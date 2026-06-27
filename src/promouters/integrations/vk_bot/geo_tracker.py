"""Periodic geo-location request scheduler for active promoter sessions.

Monitors active sessions and sends geo-location requests via VK API
at a configurable interval (default 30 min, range 20-40). Handles
reminders on timeout and logs missed pings.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6
"""
from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from promouters.db.session import SessionLocal
from promouters.models.enums import GeoPingSource, PromoterSessionStatus
from promouters.models.routing import GeoPing, PromoterSession, Route
from promouters.models.users import User

logger = logging.getLogger(__name__)

# Timeout before sending a reminder (seconds)
REMINDER_TIMEOUT_SECONDS = 5 * 60  # 5 minutes

# VK conversation peer_id offset for group chats
VK_CHAT_PEER_OFFSET = 2_000_000_000


@dataclass
class PendingRequest:
    """Tracks a pending geo request for a user."""

    sent_at: datetime
    session_id: str
    route_id: str
    promoter_id: str
    reminder_sent: bool = False


@dataclass
class SessionTrackingState:
    """Tracks the scheduling state for an active session."""

    last_ping_at: datetime  # Time of last successful geo ping or session start
    next_request_at: datetime  # When to send next geo request


class GeoTracker:
    """Periodic geo-location request scheduler for active sessions.

    Sends geo requests to promoters at a configured interval, handles
    reminder after 5 min timeout, logs missed ping after 2nd timeout,
    and cancels tracking when session leaves active status.
    """

    def __init__(self, vk_api, interval_minutes: int = 30):
        """Initialize the GeoTracker.

        Args:
            vk_api: VK API object with messages.send method.
            interval_minutes: Interval between geo requests (20-40 minutes).
        """
        if not (20 <= interval_minutes <= 40):
            raise ValueError("interval_minutes must be between 20 and 40")

        self.vk_api = vk_api
        self.interval = interval_minutes
        self.interval_seconds = interval_minutes * 60

        # user_id (int, VK) -> pending request info
        self.pending_requests: dict[int, PendingRequest] = {}

        # session_id -> scheduling state
        self._session_states: dict[str, SessionTrackingState] = {}

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # Poll interval for the background loop (seconds)
        self._poll_interval = 10

    def start(self) -> None:
        """Start background tracking thread."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("GeoTracker is already running")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="GeoTracker",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "GeoTracker started (interval=%d min, poll=%ds)",
            self.interval,
            self._poll_interval,
        )

    def stop(self) -> None:
        """Stop tracking on session end or status change."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=30)
            self._thread = None

        with self._lock:
            self.pending_requests.clear()
            self._session_states.clear()

        logger.info("GeoTracker stopped")

    def on_geo_received(self, user_id: int, lat: float, lon: float, accuracy: float | None = None) -> None:
        """Handle received geo ping, forward to work chat.

        Creates a GeoPing record with source 'tracking' and forwards
        the location to the branch work chat.

        Args:
            user_id: VK user ID of the promoter.
            lat: Latitude of the received location.
            lon: Longitude of the received location.
            accuracy: Optional accuracy in meters.
        """
        with self._lock:
            pending = self.pending_requests.pop(user_id, None)

        if pending is None:
            logger.debug("Geo received from user %d but no pending request", user_id)
            return

        now = datetime.now(UTC)

        # Create GeoPing record in DB
        db: Session = SessionLocal()
        try:
            geo_ping = GeoPing(
                session_id=pending.session_id,
                route_id=pending.route_id,
                promoter_id=pending.promoter_id,
                captured_at=now,
                latitude=lat,
                longitude=lon,
                accuracy_meters=accuracy,
                source=GeoPingSource.TRACKING,
            )
            db.add(geo_ping)
            db.commit()

            logger.info(
                "GeoPing recorded: user=%d, session=%s, lat=%.6f, lon=%.6f",
                user_id, pending.session_id, lat, lon,
            )

            # Update session tracking state: reset next request time
            with self._lock:
                if pending.session_id in self._session_states:
                    self._session_states[pending.session_id].last_ping_at = now
                    self._session_states[pending.session_id].next_request_at = datetime.fromtimestamp(
                        now.timestamp() + self.interval_seconds, tz=UTC
                    )

            # Forward location to branch work chat
            self._forward_to_work_chat(db, pending, lat, lon)

        except Exception:
            db.rollback()
            logger.exception("Error saving GeoPing for user %d", user_id)
        finally:
            db.close()

    def cancel_for_user(self, user_id: int) -> None:
        """Cancel tracking for a specific user (e.g., session ended).

        Removes any pending request and session state for the user.

        Args:
            user_id: VK user ID to cancel tracking for.
        """
        with self._lock:
            pending = self.pending_requests.pop(user_id, None)
            if pending is not None:
                self._session_states.pop(pending.session_id, None)
                logger.info("Tracking cancelled for user %d (session %s)", user_id, pending.session_id)

    def cancel_for_session(self, session_id: str) -> None:
        """Cancel tracking for a specific session.

        Args:
            session_id: Session ID to cancel tracking for.
        """
        with self._lock:
            self._session_states.pop(session_id, None)
            # Also remove from pending_requests
            to_remove = [
                uid for uid, p in self.pending_requests.items()
                if p.session_id == session_id
            ]
            for uid in to_remove:
                del self.pending_requests[uid]
                logger.info("Tracking cancelled for session %s (user %d)", session_id, uid)

    def _run_loop(self) -> None:
        """Background thread main loop."""
        logger.debug("GeoTracker loop started")
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception:
                logger.exception("Error in GeoTracker tick")

            # Sleep in small increments to allow quick shutdown
            for _ in range(self._poll_interval):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

        logger.debug("GeoTracker loop exited")

    def _tick(self) -> None:
        """Single iteration of the tracking loop.

        1. Query active sessions from DB
        2. Remove tracking for sessions that left active status
        3. Send geo requests for sessions that are due
        4. Handle pending request timeouts (reminders and missed pings)
        """
        db: Session = SessionLocal()
        try:
            now = datetime.now(UTC)

            # Query all active sessions with their routes and promoters
            active_sessions = db.scalars(
                select(PromoterSession)
                .options(
                    joinedload(PromoterSession.route).joinedload(Route.branch),
                    joinedload(PromoterSession.promoter),
                )
                .where(PromoterSession.status == PromoterSessionStatus.ACTIVE)
            ).unique().all()

            active_session_ids = {str(s.id) for s in active_sessions}

            with self._lock:
                # Remove tracking for sessions that are no longer active (Req 7.6)
                stale_sessions = [
                    sid for sid in self._session_states
                    if sid not in active_session_ids
                ]
                for sid in stale_sessions:
                    self._session_states.pop(sid)
                    # Remove from pending
                    to_remove = [
                        uid for uid, p in self.pending_requests.items()
                        if p.session_id == sid
                    ]
                    for uid in to_remove:
                        del self.pending_requests[uid]
                    logger.info("Session %s left active status, tracking cancelled", sid)

            # Process each active session
            for session in active_sessions:
                session_id = str(session.id)

                # Get VK user_id for the promoter
                promoter = session.promoter
                if promoter is None or not promoter.vk_id:
                    continue

                try:
                    vk_user_id = int(promoter.vk_id)
                except (ValueError, TypeError):
                    continue

                with self._lock:
                    # Initialize tracking state for new sessions
                    if session_id not in self._session_states:
                        started_at = session.started_at or now
                        next_request = datetime.fromtimestamp(
                            started_at.timestamp() + self.interval_seconds, tz=UTC
                        )
                        self._session_states[session_id] = SessionTrackingState(
                            last_ping_at=started_at,
                            next_request_at=next_request,
                        )

                    state = self._session_states[session_id]

                    # Check if it's time to send a geo request
                    if vk_user_id not in self.pending_requests and now >= state.next_request_at:
                        # Send geo request (Req 7.1)
                        self._send_geo_request(vk_user_id, session, promoter)
                        self.pending_requests[vk_user_id] = PendingRequest(
                            sent_at=now,
                            session_id=session_id,
                            route_id=str(session.route_id),
                            promoter_id=str(session.promoter_id),
                        )

            # Handle pending request timeouts
            self._handle_timeouts(db, now)

        except Exception:
            logger.exception("Error in GeoTracker tick")
        finally:
            db.close()

    def _handle_timeouts(self, db: Session, now: datetime) -> None:
        """Handle pending geo request timeouts.

        - After 5 min: send reminder (Req 7.4)
        - After 10 min total: log missed ping, resume interval (Req 7.5)
        """
        with self._lock:
            to_remove: list[int] = []

            for user_id, pending in self.pending_requests.items():
                elapsed = (now - pending.sent_at).total_seconds()

                if not pending.reminder_sent and elapsed >= REMINDER_TIMEOUT_SECONDS:
                    # Send reminder after 5 min (Req 7.4)
                    self._send_reminder(user_id)
                    pending.reminder_sent = True

                elif pending.reminder_sent and elapsed >= REMINDER_TIMEOUT_SECONDS * 2:
                    # 10 min total elapsed - log missed ping (Req 7.5)
                    to_remove.append(user_id)
                    self._log_missed_ping(db, pending)

                    # Resume regular interval from the original scheduled time
                    session_id = pending.session_id
                    if session_id in self._session_states:
                        state = self._session_states[session_id]
                        state.next_request_at = datetime.fromtimestamp(
                            state.next_request_at.timestamp() + self.interval_seconds, tz=UTC
                        )

            for user_id in to_remove:
                del self.pending_requests[user_id]

    def _send_geo_request(self, user_id: int, session: PromoterSession, promoter: User) -> None:
        """Send a VK message requesting geolocation from the promoter.

        Args:
            user_id: VK user ID to send the request to.
            session: Active promoter session.
            promoter: Promoter user object.
        """
        try:
            from vk_api.utils import get_random_id

            self.vk_api.messages.send(
                user_id=user_id,
                message="Отправьте геолокацию",
                random_id=get_random_id(),
            )
            logger.info("Geo request sent to user %d (session %s)", user_id, session.id)
        except Exception:
            logger.exception("Failed to send geo request to user %d", user_id)

    def _send_reminder(self, user_id: int) -> None:
        """Send a reminder message after 5 min timeout.

        Args:
            user_id: VK user ID to send the reminder to.
        """
        try:
            from vk_api.utils import get_random_id

            self.vk_api.messages.send(
                user_id=user_id,
                message="Напоминание: отправьте геолокацию",
                random_id=get_random_id(),
            )
            logger.info("Geo reminder sent to user %d", user_id)
        except Exception:
            logger.exception("Failed to send geo reminder to user %d", user_id)

    def _log_missed_ping(self, db: Session, pending: PendingRequest) -> None:
        """Log a missed geo ping event in the session summary.

        Args:
            db: Database session.
            pending: The pending request that was not answered.
        """
        try:
            session = db.get(PromoterSession, pending.session_id)
            if session is not None:
                missed_at = datetime.now(UTC).isoformat()
                note = f"Missed geo ping at {missed_at}"
                if session.summary:
                    session.summary += f"\n{note}"
                else:
                    session.summary = note
                db.add(session)
                db.commit()
                logger.warning(
                    "Missed geo ping: session=%s, promoter=%s",
                    pending.session_id, pending.promoter_id,
                )
        except Exception:
            db.rollback()
            logger.exception("Error logging missed ping for session %s", pending.session_id)

    def _forward_to_work_chat(self, db: Session, pending: PendingRequest, lat: float, lon: float) -> None:
        """Forward the received location to the branch work chat.

        Uses VK API to send the location message to the work chat
        associated with the promoter's branch.

        Args:
            db: Database session.
            pending: The pending request with session/route info.
            lat: Latitude to forward.
            lon: Longitude to forward.
        """
        try:
            # Get the branch work chat ID from environment
            # Format: VK_WORK_CHAT_<branch_id> or a single VK_WORK_CHAT_ID
            route = db.get(Route, pending.route_id)
            if route is None:
                return

            branch_id = route.branch_id

            # Try branch-specific chat first, then fall back to global
            chat_id_str = os.getenv(f"VK_WORK_CHAT_{branch_id}") or os.getenv("VK_WORK_CHAT_ID")
            if not chat_id_str:
                logger.debug("No work chat configured for branch %s", branch_id)
                return

            try:
                chat_id = int(chat_id_str)
            except (ValueError, TypeError):
                logger.warning("Invalid work chat ID: %s", chat_id_str)
                return

            # VK peer_id for group chats is 2000000000 + chat_id
            peer_id = VK_CHAT_PEER_OFFSET + chat_id

            # Load promoter name for the message
            promoter = db.get(User, pending.promoter_id)
            promoter_name = ""
            if promoter:
                promoter_name = promoter.full_name or promoter.name or f"ID {pending.promoter_id}"

            from vk_api.utils import get_random_id

            message = f"📍 Геолокация ({promoter_name}): {lat:.6f}, {lon:.6f}"
            self.vk_api.messages.send(
                peer_id=peer_id,
                message=message,
                lat=lat,
                long=lon,
                random_id=get_random_id(),
            )
            logger.info(
                "Location forwarded to work chat %d for promoter %s",
                chat_id, pending.promoter_id,
            )
        except Exception:
            logger.exception("Failed to forward location to work chat")

"""Фоновый планировщик для отправки фотонапоминаний промоутерам.

По требованию ТЗ напоминания приходят каждые 15-30 минут в псевдослучайном
порядке. Реализовано как asyncio task, запускающийся в FastAPI lifespan.
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from promouters.core.config import Settings
from promouters.db.session import SessionLocal
from promouters.models.enums import PromoterSessionStatus
from promouters.models.routing import PromoterSession, Route
from promouters.models.users import User
from promouters.services.notifications import create_notification

logger = logging.getLogger(__name__)


def _full_name(user: User | None) -> str:
    if user is None:
        return ""
    full_name = " ".join(part for part in [user.first_name, user.last_name] if part).strip()
    return full_name or user.username


def _send_due_reminders(db: Session, *, min_minutes: int, max_minutes: int) -> int:
    """Отправляет напоминания сессиям, где давно не было фотоотчёта.

    Каждой активной сессии присваивается случайный порог 15..30 минут — это и
    обеспечивает «хаотичность» напоминаний по ТЗ.
    """

    now = datetime.now(UTC)
    sent = 0

    stmt = (
        select(PromoterSession)
        .options(
            joinedload(PromoterSession.route).joinedload(Route.branch),
            joinedload(PromoterSession.promoter),
            joinedload(PromoterSession.photo_reports),
        )
        .where(PromoterSession.status == PromoterSessionStatus.ACTIVE)
    )

    sessions = list(db.scalars(stmt).unique())
    for session in sessions:
        promoter = session.promoter
        route = session.route
        if promoter is None or route is None or session.started_at is None:
            continue

        latest_photo_time = max(
            (photo.captured_at for photo in session.photo_reports),
            default=session.started_at,
        )
        since_last_minutes = (now - latest_photo_time).total_seconds() / 60.0

        threshold = random.uniform(float(min_minutes), float(max_minutes))
        if since_last_minutes < threshold:
            continue

        create_notification(
            db,
            user=promoter,
            title="Photo report reminder",
            body=f"Please upload a photo report for route '{route.title}'.",
            payload={
                "event": "photo_report.reminder",
                "route_id": str(route.id),
                "session_id": str(session.id),
                "since_last_photo_minutes": round(since_last_minutes, 1),
            },
            actor_user=None,
            branch_id=route.branch_id,
        )
        sent += 1

    if sent:
        db.commit()
    return sent


async def _photo_reminders_loop(settings: Settings) -> None:
    min_minutes = max(1, int(settings.photo_report_reminder_min_minutes))
    max_minutes = max(min_minutes, int(settings.photo_report_reminder_max_minutes))

    while True:
        try:
            db = SessionLocal()
            try:
                sent = _send_due_reminders(db, min_minutes=min_minutes, max_minutes=max_minutes)
                if sent:
                    logger.info("photo_reminders.sent count=%s", sent)
            finally:
                db.close()
        except Exception:  # noqa: BLE001 - фон не должен убивать приложение
            logger.exception("photo_reminders.loop_error")

        sleep_seconds = random.uniform(min_minutes * 60.0, max_minutes * 60.0)
        try:
            await asyncio.sleep(sleep_seconds)
        except asyncio.CancelledError:
            break


@asynccontextmanager
async def lifespan(app: FastAPI, *, settings: Settings) -> AsyncIterator[None]:
    task: asyncio.Task[None] | None = None
    if settings.photo_report_reminders_enabled:
        task = asyncio.create_task(_photo_reminders_loop(settings))
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

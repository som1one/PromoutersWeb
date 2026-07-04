from __future__ import annotations

import math
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from promouters.integrations.vk_bot.reminders import send_photo_report_reminder
from promouters.models.enums import PayoutRateType, PromoterSessionStatus, RouteStatus
from promouters.models.routing import PromoterSession, Route
from promouters.models.users import User
from promouters.services.finance import calculate_payout_for_route, get_payment_details_for_user, upsert_payment_details
from promouters.schemas.finance import PromoterPaymentDetailsCreate


class RouteCommandHandler:
    """Handles route-related commands from VK bot.

    Processes shift management commands: starting a shift, finishing a shift,
    entering leaflet count for per-unit rate type, and collecting payment details.
    """

    # Class-level dict tracking promoters awaiting leaflet input
    _awaiting_leaflet: dict[int, PromoterSession] = {}
    # Class-level dict tracking promoters in payment details collection flow
    # Format: {user_id: {"step": "confirm"|"phone"|"bank"|"name", "data": {...}}}
    _awaiting_payment_details: dict[int, dict] = {}

    def __init__(self, db: Session) -> None:
        self.db = db

    def _find_promoter(self, user_id: int) -> "User | None":
        """Look up promoter by VK user_id (checks both vk_id and tg_id fields)."""
        promoter = self.db.scalar(
            select(User).where(User.vk_id == str(user_id))
        )
        if promoter is None:
            # Fallback: VK ID stored in tg_id field (legacy registration form)
            promoter = self.db.scalar(
                select(User).where(User.tg_id == user_id)
            )
        return promoter

    def handle_start_shift(self, user_id: int, geo: dict | None) -> str:
        """Process 'В работе' command.

        Looks up the promoter by VK user_id, finds an assigned route for today,
        creates a new active session, and transitions the route to in_progress.

        Args:
            user_id: VK user ID of the promoter.
            geo: Optional dict with 'latitude' and 'longitude' keys.

        Returns:
            Confirmation message or error description.
        """
        # Look up promoter by VK user_id
        promoter = self._find_promoter(user_id)
        if promoter is None:
            return "Пользователь не найден в системе."

        # Check for existing active session
        active_session = self.db.scalar(
            select(PromoterSession).where(
                PromoterSession.promoter_id == promoter.id,
                PromoterSession.status == PromoterSessionStatus.ACTIVE,
            )
        )
        if active_session is not None:
            return "У вас уже есть активная смена. Завершите её перед началом новой."

        # Find assigned route for today
        today = date.today()
        route = self.db.scalar(
            select(Route).where(
                Route.promoter_id == promoter.id,
                Route.work_date == today,
                Route.status == RouteStatus.ASSIGNED,
            )
        )
        if route is None:
            return "На сегодня нет назначенных маршрутов."

        # Create new active session
        now = datetime.now(UTC)
        session = PromoterSession(
            route_id=route.id,
            promoter_id=promoter.id,
            started_at=now,
            status=PromoterSessionStatus.ACTIVE,
        )

        # Record geo coordinates if provided
        if geo is not None:
            session.started_latitude = geo.get("latitude")
            session.started_longitude = geo.get("longitude")

        self.db.add(session)

        # Update route status to in_progress
        route.status = RouteStatus.IN_PROGRESS
        self.db.add(route)

        self.db.commit()

        # Format confirmation message
        start_time = now.strftime("%H:%M")
        return f"Смена начата: {route.title}, {start_time}"

    def handle_finish_shift(self, user_id: int, geo: dict | None) -> str:
        """Process 'Завершить' command.

        Finds the active session for the promoter, records end time and geo,
        calculates total_minutes, and triggers payout calculation (or prompts
        for leaflet count if per_leaflet rate type).

        Args:
            user_id: VK user ID of the promoter.
            geo: Optional dict with 'latitude' and 'longitude' keys.

        Returns:
            Completion message with time/amount, or error description.
        """
        # Look up promoter by VK user_id
        promoter = self._find_promoter(user_id)
        if promoter is None:
            return "Пользователь не найден в системе."

        # Find active session for promoter
        active_session = self.db.scalar(
            select(PromoterSession).where(
                PromoterSession.promoter_id == promoter.id,
                PromoterSession.status == PromoterSessionStatus.ACTIVE,
            )
        )
        if active_session is None:
            return "У вас нет активной смены."

        # Record ended_at and calculate total_minutes
        now = datetime.now(UTC)
        active_session.ended_at = now
        total_minutes = math.floor((now - active_session.started_at).total_seconds() / 60)
        active_session.total_minutes = total_minutes

        # Record geo coordinates if provided
        if geo is not None:
            active_session.finished_latitude = geo.get("latitude")
            active_session.finished_longitude = geo.get("longitude")

        # Load route with payout_rate eagerly
        route = self.db.scalar(
            select(Route)
            .options(joinedload(Route.payout_rate))
            .where(Route.id == active_session.route_id)
        )

        # Check if payout rate is configured
        payout_rate = route.payout_rate if route else None

        # Handle per_leaflet rate: keep session active, prompt for quantity
        if payout_rate is not None and payout_rate.rate_type == PayoutRateType.PER_LEAFLET:
            # Session stays active, ended_at is recorded but status remains active
            self.db.add(active_session)
            self.db.commit()
            # Store in awaiting dict for leaflet input
            RouteCommandHandler._awaiting_leaflet[user_id] = active_session
            return "Введите количество выполненных единиц (от 1 до 100000):"

        # For hourly and fixed_shift: complete the session
        active_session.status = PromoterSessionStatus.COMPLETED
        self.db.add(active_session)

        # Update route status to completed
        if route is not None:
            route.status = RouteStatus.COMPLETED
            self.db.add(route)

        self.db.flush()

        # Handle no payout rate
        if payout_rate is None:
            self.db.commit()
            # Send photo report reminder even without a payout rate
            send_photo_report_reminder(promoter.vk_id)
            return "Тариф не настроен, расчёт не выполнен."

        # Calculate payout for hourly and fixed_shift rates
        payout = calculate_payout_for_route(
            self.db,
            route=route,
            session=active_session,
            actor_user=promoter,
            request=None,
        )

        self.db.commit()

        # Send photo report reminder after session completion
        send_photo_report_reminder(promoter.vk_id)

        # Format confirmation message
        hours = total_minutes // 60
        minutes = total_minutes % 60

        if payout is not None:
            amount = payout.amount
            result_msg = f"Смена завершена.\nВы отработали: {hours}ч {minutes}мин.\nК выплате: {amount} ₽"
            # Start payment details collection flow
            payment_msg = self._start_payment_details_flow(user_id, promoter)
            if payment_msg:
                result_msg += f"\n\n{payment_msg}"
            return result_msg
        else:
            # Payout calculation returned None (shouldn't happen if rate is configured, but handle gracefully)
            return "Тариф не настроен, расчёт не выполнен."

    def handle_leaflet_count(self, user_id: int, text: str) -> str:
        """Process quantity input for per_leaflet rate type.

        Validates the input is an integer in [1, 100000], records it in the
        session, completes the session, and triggers payout calculation.

        Args:
            user_id: VK user ID of the promoter.
            text: Raw text input from the promoter (expected to be a number).

        Returns:
            Confirmation message with amount and unit count, or validation error.
        """
        # Check if user is awaiting leaflet input
        if user_id not in RouteCommandHandler._awaiting_leaflet:
            return "Введите число от 1 до 100000."

        # Validate input is an integer in [1, 100000]
        try:
            count = int(text.strip())
        except (ValueError, TypeError):
            return "Введите число от 1 до 100000."

        if count < 1 or count > 100000:
            return "Введите число от 1 до 100000."

        # Get the session from the awaiting dict
        session = RouteCommandHandler._awaiting_leaflet[user_id]

        # Refresh session in current db context
        session = self.db.merge(session)

        # Record leaflet_count and complete the session
        session.leaflet_count = count
        session.status = PromoterSessionStatus.COMPLETED
        self.db.add(session)

        # Load route and set status to completed
        route = self.db.scalar(
            select(Route)
            .options(joinedload(Route.payout_rate))
            .where(Route.id == session.route_id)
        )
        if route is not None:
            route.status = RouteStatus.COMPLETED
            self.db.add(route)

        self.db.flush()

        # Look up promoter for the payout calculation
        promoter = self._find_promoter(user_id)

        # Calculate payout
        payout = calculate_payout_for_route(
            self.db,
            route=route,
            session=session,
            actor_user=promoter,
            request=None,
        )

        # Remove from awaiting dict
        del RouteCommandHandler._awaiting_leaflet[user_id]

        self.db.commit()

        # Send photo report reminder after session completion
        send_photo_report_reminder(promoter.vk_id if promoter else None)

        # Return confirmation message
        if payout is not None:
            amount = payout.amount
            result_msg = f"Смена завершена.\nРасчёт: {amount} ₽ за {count} шт."
            # Start payment details collection flow
            payment_msg = self._start_payment_details_flow(user_id, promoter)
            if payment_msg:
                result_msg += f"\n\n{payment_msg}"
            return result_msg
        else:
            return "Тариф не настроен, расчёт не выполнен."

    def _start_payment_details_flow(self, user_id: int, promoter: User) -> str:
        """Start payment details collection after payout calculation.

        If promoter already has saved payment details, ask if they're still valid.
        If not, start collecting from scratch.

        Returns:
            Message to send to the promoter about payment details.
        """
        existing = get_payment_details_for_user(self.db, promoter.id)

        if existing and existing.is_active:
            # Show existing details and ask for confirmation
            RouteCommandHandler._awaiting_payment_details[user_id] = {
                "step": "confirm",
                "data": {
                    "phone_number": existing.phone_number,
                    "bank_name": existing.bank_name,
                    "card_holder_name": existing.card_holder_name,
                },
                "promoter_id": str(promoter.id),
            }
            return (
                f"Реквизиты для выплаты:\n"
                f"📱 Телефон: {existing.phone_number}\n"
                f"🏦 Банк: {existing.bank_name}\n"
                f"👤 Имя: {existing.card_holder_name}\n\n"
                f"Реквизиты актуальны? (Да / Нет)"
            )
        else:
            # Start collecting new details
            RouteCommandHandler._awaiting_payment_details[user_id] = {
                "step": "phone",
                "data": {},
                "promoter_id": str(promoter.id),
            }
            return "Введите номер телефона для выплаты (СБП):"

    def handle_payment_details_input(self, user_id: int, text: str) -> str | None:
        """Process payment details input from promoter.

        Handles the multi-step flow:
        1. confirm — "Да" keeps existing, "Нет" starts new collection
        2. phone — collect phone number
        3. bank — collect bank name
        4. name — collect cardholder name, save to DB

        Args:
            user_id: VK user ID of the promoter.
            text: User's text input.

        Returns:
            Response message, or None if user is not in payment details flow.
        """
        if user_id not in RouteCommandHandler._awaiting_payment_details:
            return None

        state = RouteCommandHandler._awaiting_payment_details[user_id]
        step = state["step"]
        cleaned = text.strip()

        if step == "confirm":
            lower = cleaned.lower()
            if lower in ("да", "yes", "1", "ок", "ok"):
                # Details confirmed, done
                del RouteCommandHandler._awaiting_payment_details[user_id]
                return "✅ Реквизиты подтверждены. Выплата будет произведена на указанные данные."
            elif lower in ("нет", "no", "0"):
                # Start collecting new details
                state["step"] = "phone"
                state["data"] = {}
                return "Введите номер телефона для выплаты (СБП):"
            else:
                return "Введите «Да» или «Нет»."

        elif step == "phone":
            # Validate phone — basic check: 10+ digits
            digits = "".join(c for c in cleaned if c.isdigit())
            if len(digits) < 10:
                return "Введите корректный номер телефона (минимум 10 цифр):"
            # Normalize to +7 format if starts with 8
            if digits.startswith("8") and len(digits) == 11:
                digits = "7" + digits[1:]
            if not digits.startswith("7"):
                digits = "7" + digits[-10:]
            state["data"]["phone_number"] = f"+{digits}"
            state["step"] = "bank"
            return "Введите наименование банка (например: Сбер, Тинькофф, Альфа):"

        elif step == "bank":
            if len(cleaned) < 2:
                return "Введите наименование банка (минимум 2 символа):"
            state["data"]["bank_name"] = cleaned
            state["step"] = "name"
            return "Введите имя получателя (как на карте):"

        elif step == "name":
            if len(cleaned) < 2:
                return "Введите имя получателя (минимум 2 символа):"
            state["data"]["card_holder_name"] = cleaned

            # Save to database
            promoter_id = state["promoter_id"]
            try:
                payload = PromoterPaymentDetailsCreate(
                    phone_number=state["data"]["phone_number"],
                    bank_name=state["data"]["bank_name"],
                    card_holder_name=state["data"]["card_holder_name"],
                )
                upsert_payment_details(self.db, promoter_id, payload)
            except Exception:
                del RouteCommandHandler._awaiting_payment_details[user_id]
                return "❌ Ошибка сохранения реквизитов. Попробуйте позже."

            del RouteCommandHandler._awaiting_payment_details[user_id]
            return (
                f"✅ Реквизиты сохранены:\n"
                f"📱 Телефон: {state['data']['phone_number']}\n"
                f"🏦 Банк: {state['data']['bank_name']}\n"
                f"👤 Имя: {state['data']['card_holder_name']}\n\n"
                f"Выплата будет произведена на указанные данные."
            )

        return None

    @staticmethod
    def is_awaiting_payment_details(user_id: int) -> bool:
        """Check if user is currently in payment details collection flow."""
        return user_id in RouteCommandHandler._awaiting_payment_details

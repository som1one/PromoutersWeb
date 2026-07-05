from __future__ import annotations

import math
from datetime import UTC, date, datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from promouters.integrations.vk_bot.reminders import send_photo_report_reminder
from promouters.models.enums import PayoutRateType, PayoutStatus, PromoterSessionStatus, RouteStatus
from promouters.models.finance import Payout, PayoutRate
from promouters.models.routing import PromoterSession, Route
from promouters.models.users import User
from promouters.services.finance import get_payment_details_for_user, upsert_payment_details
from promouters.schemas.finance import PromoterPaymentDetailsCreate


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# Moscow timezone (UTC+3)
MSK = timezone(timedelta(hours=3))


class RouteCommandHandler:
    """Handles route-related commands from VK bot.

    Processes shift management commands: starting a shift, finishing a shift,
    entering leaflet count for per-unit rate type, and collecting payment details.

    Works WITHOUT routes — promoter simply starts/stops a timer.
    Payout is calculated based on the promoter's branch/role payout rate.
    """

    # Class-level dict tracking promoters awaiting leaflet input
    _awaiting_leaflet: dict[int, PromoterSession] = {}
    # Class-level dict tracking promoters in payment details collection flow
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

    def _find_payout_rate(self, promoter: User) -> PayoutRate | None:
        """Find applicable payout rate for promoter (by branch + role, or branch, or global).

        Priority:
        1. Active rate matching promoter's branch_id AND role_id
        2. Active rate matching promoter's branch_id (any role)
        3. Active rate with no branch (global)
        """
        today = date.today()
        base_query = (
            select(PayoutRate)
            .where(
                PayoutRate.is_active.is_(True),
                (PayoutRate.active_from.is_(None)) | (PayoutRate.active_from <= today),
                (PayoutRate.active_to.is_(None)) | (PayoutRate.active_to >= today),
            )
        )

        # 1. Branch + role match
        if promoter.branch_id and promoter.role_id:
            rate = self.db.scalar(
                base_query.where(
                    PayoutRate.branch_id == promoter.branch_id,
                    PayoutRate.role_id == promoter.role_id,
                )
            )
            if rate:
                return rate

        # 2. Branch only
        if promoter.branch_id:
            rate = self.db.scalar(
                base_query.where(
                    PayoutRate.branch_id == promoter.branch_id,
                    PayoutRate.role_id.is_(None),
                )
            )
            if rate:
                return rate

        # 3. Global (no branch)
        rate = self.db.scalar(
            base_query.where(
                PayoutRate.branch_id.is_(None),
            )
        )
        return rate

    def handle_start_shift(self, user_id: int, geo: dict | None) -> str:
        """Process 'В работе' command.

        Creates an active session for the promoter (no route required).

        Args:
            user_id: VK user ID of the promoter.
            geo: Optional dict with 'latitude' and 'longitude' keys.

        Returns:
            Confirmation message or error description.
        """
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

        # Create new active session (without route)
        now = datetime.now(UTC)
        session = PromoterSession(
            route_id=None,
            promoter_id=promoter.id,
            started_at=now,
            status=PromoterSessionStatus.ACTIVE,
        )

        # Record geo coordinates if provided
        if geo is not None:
            session.started_latitude = geo.get("latitude")
            session.started_longitude = geo.get("longitude")

        self.db.add(session)
        self.db.commit()

        start_time = now.astimezone(MSK).strftime("%H:%M")
        return f"✅ Смена начата в {start_time}"

    def handle_finish_shift(self, user_id: int, geo: dict | None) -> str:
        """Process 'Завершить' command.

        Finds the active session, records end time, calculates payout
        based on promoter's payout rate (by branch/role).

        Args:
            user_id: VK user ID of the promoter.
            geo: Optional dict with 'latitude' and 'longitude' keys.

        Returns:
            Completion message with time/amount, or error description.
        """
        promoter = self._find_promoter(user_id)
        if promoter is None:
            return "Пользователь не найден в системе."

        # Find active session
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

        # Find payout rate for this promoter
        payout_rate = self._find_payout_rate(promoter)

        # Handle per_leaflet rate: prompt for quantity
        if payout_rate is not None and payout_rate.rate_type == PayoutRateType.PER_LEAFLET:
            self.db.add(active_session)
            self.db.commit()
            RouteCommandHandler._awaiting_leaflet[user_id] = active_session
            return "Введите количество выполненных единиц (от 1 до 100000):"

        # Complete the session
        active_session.status = PromoterSessionStatus.COMPLETED
        self.db.add(active_session)
        self.db.flush()

        # Handle no payout rate
        if payout_rate is None:
            self.db.commit()
            send_photo_report_reminder(promoter.vk_id)
            hours = total_minutes // 60
            minutes = total_minutes % 60
            return f"Смена завершена. Время: {hours}ч {minutes}мин.\nТариф не настроен, расчёт не выполнен."

        # Calculate payout
        payout = self._calculate_payout(promoter, active_session, payout_rate)
        self.db.commit()

        send_photo_report_reminder(promoter.vk_id)

        hours = total_minutes // 60
        minutes = total_minutes % 60

        if payout is not None:
            amount = payout.amount
            result_msg = f"Смена завершена.\nВы отработали: {hours}ч {minutes}мин.\nК выплате: {amount} ₽"
            payment_msg = self._start_payment_details_flow(user_id, promoter)
            if payment_msg:
                result_msg += f"\n\n{payment_msg}"
            return result_msg
        else:
            return f"Смена завершена. Время: {hours}ч {minutes}мин.\nОшибка расчёта."

    def handle_leaflet_count(self, user_id: int, text: str) -> str:
        """Process quantity input for per_leaflet rate type."""
        if user_id not in RouteCommandHandler._awaiting_leaflet:
            return "Введите число от 1 до 100000."

        try:
            count = int(text.strip())
        except (ValueError, TypeError):
            return "Введите число от 1 до 100000."

        if count < 1 or count > 100000:
            return "Введите число от 1 до 100000."

        session = RouteCommandHandler._awaiting_leaflet[user_id]
        session = self.db.merge(session)

        session.leaflet_count = count
        session.status = PromoterSessionStatus.COMPLETED
        self.db.add(session)
        self.db.flush()

        promoter = self._find_promoter(user_id)
        payout_rate = self._find_payout_rate(promoter) if promoter else None

        payout = None
        if payout_rate and promoter:
            payout = self._calculate_payout(promoter, session, payout_rate)

        del RouteCommandHandler._awaiting_leaflet[user_id]
        self.db.commit()

        send_photo_report_reminder(promoter.vk_id if promoter else None)

        if payout is not None:
            amount = payout.amount
            result_msg = f"Смена завершена.\nРасчёт: {amount} ₽ за {count} шт."
            if promoter:
                payment_msg = self._start_payment_details_flow(user_id, promoter)
                if payment_msg:
                    result_msg += f"\n\n{payment_msg}"
            return result_msg
        else:
            return "Тариф не настроен, расчёт не выполнен."

    def _calculate_payout(
        self,
        promoter: User,
        session: PromoterSession,
        payout_rate: PayoutRate,
    ) -> Payout | None:
        """Calculate and create payout for a completed session (without route)."""
        if payout_rate.rate_type == PayoutRateType.HOURLY:
            total_minutes = session.total_minutes or 0
            units = _quantize(Decimal(total_minutes) / Decimal(60))
            amount = _quantize(payout_rate.amount * units)
            details = {
                "rate_type": "hourly",
                "rate_amount": str(payout_rate.amount),
                "units": str(units),
                "unit_label": "hours",
                "total_minutes": total_minutes,
                "formula": f"{payout_rate.amount} * {units}",
            }
            notes = f"Почасовая: {payout_rate.amount} × {units}ч = {amount} ₽"

        elif payout_rate.rate_type == PayoutRateType.PER_LEAFLET:
            leaflet_count = session.leaflet_count or 0
            units = _quantize(Decimal(leaflet_count))
            amount = _quantize(payout_rate.amount * units)
            details = {
                "rate_type": "per_leaflet",
                "rate_amount": str(payout_rate.amount),
                "units": str(units),
                "unit_label": "leaflets",
                "leaflet_count": leaflet_count,
                "formula": f"{payout_rate.amount} * {units}",
            }
            notes = f"Поштучная: {payout_rate.amount} × {leaflet_count} шт. = {amount} ₽"

        elif payout_rate.rate_type == PayoutRateType.FIXED_SHIFT:
            units = Decimal("1")
            amount = _quantize(payout_rate.amount)
            details = {
                "rate_type": "fixed_shift",
                "rate_amount": str(payout_rate.amount),
                "units": "1",
                "unit_label": "shift",
                "formula": f"{payout_rate.amount} * 1",
            }
            notes = f"За смену: {amount} ₽"
        else:
            return None

        payout = Payout(
            route_id=None,
            session_id=str(session.id),
            promoter_id=str(promoter.id),
            payout_rate_id=str(payout_rate.id),
            amount=amount,
            currency=payout_rate.currency,
            units=units,
            notes=notes,
            calculation_details=details,
            status=PayoutStatus.CALCULATED,
            calculated_at=datetime.now(UTC),
        )
        self.db.add(payout)
        self.db.flush()
        return payout

    def _start_payment_details_flow(self, user_id: int, promoter: User) -> str:
        """Start payment details collection after payout calculation.

        If promoter already has saved payment details, ask if they're still valid.
        If not, start collecting from scratch.
        """
        existing = get_payment_details_for_user(self.db, promoter.id)

        if existing and existing.is_active:
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
                del RouteCommandHandler._awaiting_payment_details[user_id]
                return "✅ Реквизиты подтверждены. Выплата будет произведена на указанные данные."
            elif lower in ("нет", "no", "0"):
                state["step"] = "phone"
                state["data"] = {}
                return "Введите номер телефона для выплаты (СБП):"
            else:
                return "Введите «Да» или «Нет»."

        elif step == "phone":
            digits = "".join(c for c in cleaned if c.isdigit())
            if len(digits) < 10:
                return "Введите корректный номер телефона (минимум 10 цифр):"
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

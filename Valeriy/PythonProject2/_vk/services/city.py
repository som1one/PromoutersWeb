"""City creation flow for VK bot."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from model import City, User
from _vk.config import DEFAULT_TZ_NAME


@dataclass
class CityCreationState:
    step: str = "ask_name"
    name: Optional[str] = None
    timezone: Optional[str] = None
    director_id: Optional[int] = None
    master_ids: List[int] = field(default_factory=list)


class CityCreationFlow:
    """Инкапсулирует сценарий добавления города."""

    CANCEL_TOKENS: Sequence[str] = ("отмена", "cancel", "стоп")
    SKIP_TOKENS: Sequence[str] = ("-", "skip", "пропустить", "нет")

    def __init__(self, bot, states):
        self.bot = bot
        self.states = states

    # ==== Public API =======================================================

    def start(self, user_id: int) -> None:
        if self.states.get_city_creation_state(user_id):
            self.bot.send_message(user_id, "ℹ️ Продолжаем добавление города. Напишите 'отмена' для отмены.")
            return
        self.states.set_city_creation_state(
            user_id, {"step": "ask_name", "data": CityCreationState().__dict__}
        )
        self.bot.send_message(user_id, "🏙 Введите название города:\nНапишите 'отмена' для отмены.")

    def start_with_name(self, user_id: int, name: str) -> None:
        if self.states.get_city_creation_state(user_id):
            self.bot.send_message(user_id, "ℹ️ Продолжаем добавление города. Напишите 'отмена' для отмены.")
            return
        state = CityCreationState(step="ask_timezone", name=name)
        self.states.set_city_creation_state(user_id, {"step": "ask_timezone", "data": state.__dict__})
        self.bot.send_message(
            user_id,
            "🕒 Введите часовой пояс (например, Europe/Moscow).\n"
            "Чтобы использовать значение по умолчанию, напишите 'по умолчанию'.",
        )

    def create_immediate(
        self,
        user_id: int,
        session,
        name: str,
        tz_candidate: Optional[str] = None,
        director_id: Optional[int] = None,
        master_ids: Optional[Sequence[int]] = None,
    ) -> bool:
        tz_value = self._normalize_timezone_input(tz_candidate or "")
        if not tz_value:
            self.bot.send_message(
                user_id,
                "❌ Таймзона не распознана. Пример: Europe/Moscow.\n"
                "Попробуйте снова или используйте значение по умолчанию.",
            )
            return False
        return self._create_city(user_id, session, name, tz_value, director_id, master_ids)

    def handle(self, user_id: int, text: str, role: str, session) -> bool:
        state_wrapper = self.states.get_city_creation_state(user_id)
        if not state_wrapper:
            return False

        if role != "owner":
            self.states.clear_city_creation_state(user_id)
            self.bot.send_message(user_id, "🚫 Нет доступа.")
            return True

        state = CityCreationState(**(state_wrapper.get("data") or {}))
        step = state_wrapper.get("step", "ask_name")
        normalized = text.strip()
        lower = normalized.lower()

        if lower in self.CANCEL_TOKENS:
            self.states.clear_city_creation_state(user_id)
            self.bot.send_message(user_id, "❌ Добавление города отменено.", self.bot.get_keyboard(role))
            return True

        handler_name = f"_step_{step}"
        handler = getattr(self, handler_name, None)
        if not handler:
            self.states.clear_city_creation_state(user_id)
            self.bot.send_message(user_id, "❌ Ошибка состояния. Запустите добавление города заново.")
            return True

        next_step = handler(user_id, normalized, lower, state, session)
        if next_step:
            state_wrapper["step"] = next_step
            state_wrapper["data"] = state.__dict__
            self.states.set_city_creation_state(user_id, state_wrapper)
        else:
            self.states.clear_city_creation_state(user_id)
        return True

    # ==== Steps ============================================================

    def _step_ask_name(self, user_id, text, lower, state: CityCreationState, session):
        if not text:
            self.bot.send_message(user_id, "❌ Название города не может быть пустым. Попробуйте снова.")
            return "ask_name"
        if session.query(City).filter(City.name.ilike(text)).first():
            self.bot.send_message(user_id, "❌ Такой город уже существует. Введите другое название.")
            return "ask_name"
        state.name = text
        self.bot.send_message(
            user_id,
            "🕒 Введите часовой пояс (например, Europe/Moscow).\n"
            "Чтобы использовать значение по умолчанию, напишите 'по умолчанию'.",
        )
        return "ask_timezone"

    def _step_ask_timezone(self, user_id, text, lower, state: CityCreationState, session):
        tz_value = self._normalize_timezone_input(text)
        if not tz_value:
            self.bot.send_message(
                user_id,
                "❌ Таймзона не распознана. Пример: Europe/Moscow.\n"
                "Попробуйте снова или напишите 'по умолчанию'.",
            )
            return "ask_timezone"
        state.timezone = tz_value
        self.bot.send_message(
            user_id,
            "👔 Введите VK ID директора (число) или '-' чтобы пропустить.",
        )
        return "ask_director"

    def _step_ask_director(self, user_id, text, lower, state: CityCreationState, session):
        if lower not in self.SKIP_TOKENS and text:
            try:
                state.director_id = int(text)
            except ValueError:
                self.bot.send_message(user_id, "❌ Введите числовой VK ID директора или '-' чтобы пропустить.")
                return "ask_director"
        else:
            state.director_id = None

        self.bot.send_message(
            user_id,
            "🔧 Введите VK ID мастеров через запятую или '-' чтобы пропустить (пример: 123,456).",
        )
        return "ask_masters"

    def _step_ask_masters(self, user_id, text, lower, state: CityCreationState, session):
        master_ids: List[int] = []
        if lower not in self.SKIP_TOKENS and text:
            raw = [part.strip() for part in text.replace(";", ",").split(",") if part.strip()]
            if not raw:
                self.bot.send_message(
                    user_id, "❌ Укажите VK ID мастеров через запятую или '-' чтобы пропустить."
                )
                return "ask_masters"
            try:
                master_ids = [int(part) for part in raw]
            except ValueError:
                self.bot.send_message(
                    user_id, "❌ Укажите VK ID мастеров числом через запятую или '-' чтобы пропустить."
                )
                return "ask_masters"
        state.master_ids = master_ids

        if not state.name:
            self.bot.send_message(user_id, "❌ Ошибка состояния. Начните заново.")
            return None

        success = self._create_city(
            user_id,
            session,
            state.name,
            state.timezone or DEFAULT_TZ_NAME,
            state.director_id,
            state.master_ids,
        )
        if success:
            self.bot.send_message(user_id, "🏙 Город успешно создан.", self.bot.get_keyboard("owner"))
        return None

    # ==== Helpers =========================================================

    def _normalize_timezone_input(self, tz_input: str) -> Optional[str]:
        tz_raw = (tz_input or "").strip()
        if not tz_raw or tz_raw.lower() in (
            "default",
            "defaults",
            "по умолчанию",
            "поумолчанию",
            "умолчанию",
            "умолчание",
            "по",
            "-",
            "skip",
        ):
            tz_raw = DEFAULT_TZ_NAME
        try:
            ZoneInfo(tz_raw)
        except ZoneInfoNotFoundError:
            return None
        except Exception:
            return None
        return tz_raw

    def _create_city(
        self,
        user_id: int,
        session,
        name: str,
        tz: str,
        director_id: Optional[int],
        master_ids: Optional[Sequence[int]],
    ) -> bool:
        city = City(name=name.strip(), timezone=tz)
        session.add(city)
        try:
            session.flush()

            summary_lines = [
                f"✅ Город добавлен: {city.name}",
                f"🕒 Часовой пояс: {tz}",
                f"🆔 ID: {city.id}",
            ]

            if director_id:
                director = session.query(User).filter_by(tg_id=director_id).first()
                if not director:
                    director = User(tg_id=director_id, name=str(director_id))
                    session.add(director)
                    session.flush()
                director.role = "director"
                director.city_id = city.id
                summary_lines.append(f"👔 Директор: {director_id}")

            added_masters: List[str] = []
            for master_id in sorted(set([m for m in master_ids or [] if m is not None])):
                master = session.query(User).filter_by(tg_id=master_id).first()
                if not master:
                    master = User(tg_id=master_id, name=str(master_id))
                    session.add(master)
                    session.flush()
                master.role = "master"
                master.city_id = city.id
                added_masters.append(str(master_id))

            session.commit()
            if added_masters:
                summary_lines.append(f"🔧 Мастера: {', '.join(added_masters)}")
            self.bot.send_message(user_id, "\n".join(summary_lines))
            return True
        except Exception as exc:
            session.rollback()
            self.bot.logger.exception("Ошибка при создании города")
            self.bot.send_message(user_id, f"❌ Не удалось создать город: {exc}")
            return False


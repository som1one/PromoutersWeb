"""
Обработчики для работы с формами заявок.
Содержит логику заполнения и редактирования заявок.
"""

import logging
from typing import Dict, Any, List, Optional
from telebot import types
from db import get_session
from handlers.utils import get_equip_type_name
from services.user_service import get_role, require_role, generate_order_number
from handlers.menu_kb import (
    equip_type_keyboard, cancel_keyboard, edit_order_keyboard,
    master_selection_keyboard, city_selection_keyboard
)
from model import User, Order, City
from _vk.state_manager import user_states

logger = logging.getLogger(__name__)


class FormHandler:
    """Класс для обработки форм заявок"""
    
    def __init__(self, bot):
        self.bot = bot
        self.states = user_states
    
    def start_form(self, message: types.Message) -> None:
        """Начать заполнение формы заявки"""
        session = get_session()
        try:
            if not require_role(session, message.from_user.id, ("dispatcher",)):
                self.bot.reply_to(message, "🚫 Только диспетчер может создавать заявки.")
                return
            
            cities = session.query(City).all()
            if not cities:
                self.bot.send_message(message.chat.id, "❌ Нет городов! Обратитесь к администратору.")
                return
            
            self.states.set_form_state(message.from_user.id, {
                "step": "city_selection", 
                "data": {"is_warranty": False}
            })
            kb = city_selection_keyboard(cities)
            self.bot.send_message(message.chat.id, "🏙 Выберите город для заявки:", reply_markup=kb)
        finally:
            session.close()
    
    def fill_form(self, message: types.Message) -> None:
        """Обработать заполнение формы"""
        user_id = message.from_user.id
        state = self.states.get_form_state(user_id)
        if not state:
            return
        
        step = state["step"]
        data = state["data"]
        text = message.text.strip()
        session = get_session()
        
        try:
            role = get_role(session, user_id)
            
            steps = [
                "city_selection", "street", "house", "flat", "time_from", "time_to", 
                "equip_type", "short_desc", "source", "client_name", 
                "client_phone", "comment", "master_selection", "order_date"
            ]
            
            prompts = [
                "🏙 Выберите город для заявки:",  # city_selection - не используется, так как это инлайн кнопки
                "📍 Введите улицу (например: Красная, Ленина, Советская):",
                "🏠 Введите номер дома (например: 15, 25а, 100/2):",
                "🚪 Введите квартиру или ЧД (например: 25, ЧД, -):",
                "⏰ Введите время от (например: 09:00, 14:30, 17:00):",
                "⏰ Введите время до (например: 10:00, 15:30, 18:00):",
                "🔧 Выберите тип техники:",
                "📝 Введите краткое описание проблемы (например: не включается, не работает звук, зависает):",
                "📞 Введите имя источника (например: Роман, Яндекс, сайт):",
                "👤 Введите ФИО клиента (например: Иванов Иван Иванович):",
                "📱 Введите телефон клиента (например: +7(999)123-45-67):",
                "💬 Введите комментарий (необязательно, например: можно раньше, представился Романом):",
                "🔧 Выберите мастера для назначения заявки:",
                "📅 Введите дату выполнения (например: 25.12.2024 или 'сегодня' для сегодняшней даты):",
            ]
            
            idx = steps.index(step)
            
            if step == "city_selection":
                # Шаг выбора города обрабатывается через инлайн кнопки, не через текстовый ввод
                self.bot.send_message(message.chat.id, "❌ Пожалуйста, выберите город из списка выше")
                return
            
            if step == "equip_type":
                kb = equip_type_keyboard()
                self.bot.send_message(message.chat.id, prompts[idx], reply_markup=kb)
                return
            
            if step == "master_selection":
                # Показываем список мастеров сразу при переходе к этому шагу
                self._show_master_selection(message, user_id, session, data, role)
                return
            
            # Для комментария можно пропустить (оставить пустым)
            if step == "comment" and not text.strip():
                data[step] = ""
            elif step == "order_date":
                # Обработка даты
                from datetime import datetime
                if text.lower() == "сегодня":
                    data[step] = datetime.now().date()
                else:
                    try:
                        # Пытаемся распарсить дату в формате DD.MM.YYYY
                        date_obj = datetime.strptime(text, "%d.%m.%Y").date()
                        data[step] = date_obj
                    except ValueError:
                        self.bot.send_message(message.chat.id, "❌ Неверный формат даты. Используйте DD.MM.YYYY или 'сегодня'")
                        return
            else:
                data[step] = text
            
            # Проверяем, редактируем ли мы поле или заполняем форму впервые
            if state.get("editing", False):
                self._return_to_preview(message, user_id, session)
                return
            
            if idx + 1 < len(steps):
                next_step = steps[idx + 1]
                state["step"] = next_step
                
                # Для шага выбора мастера показываем список сразу
                if next_step == "master_selection":
                    self._show_master_selection(message, user_id, session, data, role)
                    return
                
                # Для шага выбора типа техники показываем инлайн кнопки сразу
                if next_step == "equip_type":
                    kb = equip_type_keyboard()
                    self.bot.send_message(message.chat.id, prompts[idx + 1], reply_markup=kb)
                    return
                
                kb = cancel_keyboard()
                self.bot.send_message(message.chat.id, prompts[idx + 1], reply_markup=kb)
                return
            
            # Показать подтверждение
            self._show_order_preview(message, user_id, session)
            
        finally:
            session.close()
    
    def _get_available_masters(self, session, role: str) -> List[User]:
        """Получить список доступных мастеров в зависимости от роли"""
        if role == "dispatcher":
            return session.query(User).filter_by(role="master").all()
        elif role == "director":
            return session.query(User).filter_by(role="master").all()
        else:
            return session.query(User).filter_by(role="master").all()
    
    def _get_main_keyboard(self, role: str):
        """Получить главную клавиатуру для роли"""
        from handlers.menu_kb import main_keyboard
        return main_keyboard(role)
    
    def _return_to_preview(self, message: types.Message, user_id: int, session) -> None:
        """Вернуться к предварительному просмотру заявки"""
        state = self.states.get_form_state(user_id)
        if not state:
            return
        
        data = state["data"]
        
        # Получаем название типа техники по коду
        equip_type_code = data.get("equip_type", "")
        equip_type_name = get_equip_type_name(equip_type_code)
        
        # Получаем имя выбранного мастера
        assigned_to = data.get("assigned_to")
        master_name = "Не назначен"
        if assigned_to:
            master = session.query(User).filter_by(tg_id=assigned_to).first()
            master_name = master.name if master else f"ID {assigned_to}"
        
        order_data = {
            "order_number": generate_order_number(session),
            "city": data.get("city_name"),
            "city_id": data.get("city_id"),
            "street": data.get("street"),
            "house": data.get("house"),
            "flat": data.get("flat"),
            "time_from": data.get("time_from"),
            "time_to": data.get("time_to"),
            "equip_type": equip_type_name,
            "equip_type_code": equip_type_code,
            "short_desc": data.get("short_desc"),
            "source": data.get("source"),
            "client_name": data.get("client_name"),
            "client_phone": data.get("client_phone"),
            "comment": data.get("comment", ""),
            "assigned_to": assigned_to,
            "master_name": master_name,
            "is_warranty": bool(data.get("is_warranty", False)),
        }
        
        preview_text = self._format_order_preview(order_data)
        kb = edit_order_keyboard(order_data.get("is_warranty", False))
        self.bot.send_message(message.chat.id, preview_text, reply_markup=kb, parse_mode="HTML")
        
        # Сохраняем данные для подтверждения
        state["step"] = "confirm"
        state["order_data"] = order_data
        state["editing"] = False
    
    def _format_order_preview(self, order_data: Dict[str, Any]) -> str:
        """Форматировать текст предварительного просмотра заявки"""
        preview_text = f"📋 <b>Предварительный просмотр заявки:</b>\n\n"
        if order_data.get("is_warranty"):
            preview_text += "🛡 Гарантия: <b>ДА</b> (не учитывать в статистике)\n"
        preview_text += f"🏙 Город: {order_data['city']}\n"
        preview_text += f"📍 Адрес: ул. {order_data['street']}, д. {order_data['house']}, кв. {order_data['flat']}\n"
        preview_text += f"⏰ Время: {order_data['time_from']} - {order_data['time_to']}\n"
        preview_text += f"🔧 Тип техники: {order_data['equip_type']}\n"
        preview_text += f"📝 Описание: {order_data['short_desc']}\n"
        preview_text += f"📞 Источник: {order_data['source']}\n"
        preview_text += f"👤 Клиент: {order_data.get('client_name', 'Не указано')}\n"
        preview_text += f"📱 Телефон: {order_data.get('client_phone', 'Не указан')}\n"
        if order_data.get('comment'):
            preview_text += f"💬 Комментарий: {order_data['comment']}\n"
        preview_text += f"🔧 Назначен мастер: {order_data.get('master_name', 'Не назначен')}\n"
        preview_text += f"\n<b>Проверьте данные и выберите действие:</b>"
        return preview_text
    
    def _show_order_preview(self, message: types.Message, user_id: int, session) -> None:
        """Показать предварительный просмотр заявки"""
        state = self.states.get_form_state(user_id)
        if not state:
            return
        
        data = state["data"]
        
        # Получаем название типа техники по коду
        equip_type_code = data.get("equip_type", "")
        equip_type_name = get_equip_type_name(equip_type_code)
        
        # Получаем имя выбранного мастера
        assigned_to = data.get("assigned_to")
        master_name = "Не назначен"
        if assigned_to:
            master = session.query(User).filter_by(tg_id=assigned_to).first()
            master_name = master.name if master else f"ID {assigned_to}"
        
        order_data = {
            "order_number": generate_order_number(session),
            "city": data.get("city_name"),
            "city_id": data.get("city_id"),
            "street": data.get("street"),
            "house": data.get("house"),
            "flat": data.get("flat"),
            "time_from": data.get("time_from"),
            "time_to": data.get("time_to"),
            "equip_type": equip_type_name,
            "equip_type_code": equip_type_code,
            "short_desc": data.get("short_desc"),
            "source": data.get("source"),
            "client_name": data.get("client_name"),
            "client_phone": data.get("client_phone"),
            "comment": data.get("comment", ""),
            "assigned_to": assigned_to,
            "master_name": master_name,
            "is_warranty": bool(data.get("is_warranty", False)),
        }
        
        preview_text = self._format_order_preview(order_data)
        kb = edit_order_keyboard(order_data.get("is_warranty", False))
        self.bot.send_message(message.chat.id, preview_text, reply_markup=kb, parse_mode="HTML")
        
        # Сохраняем данные для подтверждения
        state["step"] = "confirm"
        state["order_data"] = order_data
    
    def handle_equip_type_callback(self, callback: types.CallbackQuery) -> None:
        """Обработать выбор типа техники"""
        session = get_session()
        try:
            user_id = callback.from_user.id
            state = self.states.get_form_state(user_id)
            if not state:
                self.bot.answer_callback_query(callback.id, "Форма не активна")
                return
            
            equip_type = callback.data.split(":")[1]
            state["data"]["equip_type"] = equip_type
            
            if state.get("editing", False):
                self.bot.edit_message_text(
                    "✅ Тип техники обновлен!", 
                    chat_id=callback.message.chat.id, 
                    message_id=callback.message.message_id
                )
                self._return_to_preview(callback.message, user_id, session)
            else:
                state["step"] = "short_desc"
                self.bot.edit_message_text(
                    "📝 Краткое описание:", 
                    chat_id=callback.message.chat.id, 
                    message_id=callback.message.message_id
                )
                kb = cancel_keyboard()
                self.bot.send_message(
                    callback.message.chat.id, 
                    "📝 Введите краткое описание проблемы (например: не включается, не работает звук, зависает):", 
                    reply_markup=kb
                )
            
            self.bot.answer_callback_query(callback.id, "Тип техники выбран")
        finally:
            session.close()
    
    def handle_cancel_form_callback(self, callback: types.CallbackQuery) -> None:
        """Обработать отмену формы"""
        session = get_session()
        try:
            user_id = callback.from_user.id
            self.states.clear_form_state(user_id)
            role = get_role(session, user_id)
            self.bot.edit_message_text(
                "❌ Создание заявки отменено", 
                chat_id=callback.message.chat.id, 
                message_id=callback.message.message_id
            )
            kb = self._get_main_keyboard(role)
            self.bot.send_message(callback.message.chat.id, "🏠 Главное меню:", reply_markup=kb)
            self.bot.answer_callback_query(callback.id, "Заявка отменена")
        finally:
            session.close()
    
    def handle_select_master_callback(self, callback: types.CallbackQuery) -> None:
        """Обработать выбор мастера"""
        session = get_session()
        try:
            user_id = callback.from_user.id
            state = self.states.get_form_state(user_id)
            if not state:
                self.bot.answer_callback_query(callback.id, "Форма не активна")
                return
            
            master_tg_id = int(callback.data.split(":")[1])
            state["data"]["assigned_to"] = master_tg_id
            
            # Получаем информацию о мастере
            master = session.query(User).filter_by(tg_id=master_tg_id).first()
            if master:
                master_name = master.full_name or master.name or f"ID {master_tg_id}"
                master_info = f"{master_name}"
                if master.city_rel:
                    master_info += f" ({master.city_rel.name})"
            else:
                master_name = f"ID {master_tg_id}"
                master_info = master_name
            
            self.bot.edit_message_text(
                f"✅ Мастер {master_info} выбран!", 
                chat_id=callback.message.chat.id, 
                message_id=callback.message.message_id
            )
            
            # Переходим к предварительному просмотру
            self._return_to_preview(callback.message, user_id, session)
            
            self.bot.answer_callback_query(callback.id, f"Мастер {master_info} выбран")
        finally:
            session.close()
    
    def handle_select_city_callback(self, callback: types.CallbackQuery) -> None:
        """Обработать выбор города для заявки"""
        session = get_session()
        try:
            user_id = callback.from_user.id
            state = self.states.get_form_state(user_id)
            if not state or state["step"] != "city_selection":
                self.bot.answer_callback_query(callback.id, "Форма не активна")
                return
            
            city_id = int(callback.data.split(":")[1])
            city = session.query(City).filter_by(id=city_id).first()
            if not city:
                self.bot.answer_callback_query(callback.id, "Город не найден!")
                return
            
            state["data"]["city_id"] = city_id
            state["data"]["city_name"] = city.name
            state["step"] = "street"
            kb = cancel_keyboard()
            self.bot.edit_message_text(
                f"✅ Город: {city.name}\n\n📍 Введите улицу:", 
                chat_id=callback.message.chat.id, 
                message_id=callback.message.message_id
            )
            self.bot.send_message(callback.message.chat.id, "📍 Введите улицу:", reply_markup=kb)
            self.bot.answer_callback_query(callback.id, f"Город выбран: {city.name}")
        finally:
            session.close()
    
    def _show_master_selection(self, message: types.Message, user_id: int, session, data: dict, role: str) -> None:
        """Показать список мастеров для выбора"""
        # Ограничиваем мастеров по городу, если он уже выбран
        city_id = data.get("city_id")
        if city_id is not None:
            masters = session.query(User).filter_by(role="master", city_id=city_id).all()
        else:
            # Если у диспетчера есть город, используем его
            disp = session.query(User).filter_by(tg_id=user_id).first()
            if role == "dispatcher" and disp and getattr(disp, 'city_id', None):
                masters = session.query(User).filter_by(role="master", city_id=disp.city_id).all()
            else:
                masters = self._get_available_masters(session, role)
        
        if not masters:
            self.bot.send_message(
                message.chat.id, 
                "❌ В системе нет мастеров. Обратитесь к администратору.", 
                reply_markup=self._get_main_keyboard(role)
            )
            self.states.clear_form_state(user_id)
            return
        
        kb = master_selection_keyboard(masters)
        self.bot.send_message(message.chat.id, "🔧 Выберите мастера для назначения заявки:", reply_markup=kb)

"""
Обработчики для разных ролей пользователей.
Содержит специфичную логику для каждой роли.
"""

import logging
from typing import List, Dict, Any
from telebot import types
from db import get_session
from services.user_service import get_role, require_role
from handlers.utils import get_equip_type_name
from handlers.menu_kb import (
    main_keyboard, admin_keyboard, create_master_keyboard,
    master_creation_method_keyboard, cancel_master_creation_keyboard,
    city_selection_keyboard, city_management_keyboard, admin_back_keyboard
)
from model import User, Order, Stat, City
from _vk.state_manager import user_states
import time

logger = logging.getLogger(__name__)


class RoleHandler:
    """Базовый класс для обработчиков ролей"""
    
    def __init__(self, bot):
        self.bot = bot
        self.states = user_states
    
    def get_main_keyboard(self, role: str):
        """Получить главную клавиатуру для роли"""
        return main_keyboard(role)


class DispatcherHandler(RoleHandler):
    """Обработчик для диспетчеров"""
    
    def handle_my_orders(self, message: types.Message) -> None:
        """Показать заявки диспетчера"""
        session = get_session()
        try:
            uid = message.from_user.id
            role = get_role(session, uid)
            
            # Диспетчеры не видят "Мои заявки"
            if role == "dispatcher":
                self.bot.reply_to(message, "🚫 У диспетчеров нет доступа к заявкам.")
                return
            
            # Определяем какие заявки показывать (только активные)
            q = session.query(Order).filter(
                Order.status.notin_(["completed", "declined"])
            )
            if role == "master":
                # Мастер видит только свои активные заявки
                orders = q.filter(Order.assigned_to == uid).order_by(Order.created_at.desc()).limit(20).all()
            elif role == "director":
                # Директор видит все активные заявки
                orders = q.order_by(Order.created_at.desc()).limit(20).all()
            else:
                # Собственник и другие видят свои активные заявки
                orders = q.filter((Order.assigned_to == uid) | (Order.created_by == uid)).order_by(Order.created_at.desc()).limit(20).all()
                
            if not orders:
                self.bot.send_message(message.chat.id, "📭 Заявок нет.", reply_markup=main_keyboard(role))
                return
                
            for o in orders:
                # Получаем название типа техники по коду
                equip_type_name = get_equip_type_name(o.equip_type)
                
                # Получаем информацию о мастере, если заявка назначена
                master_info = ""
                if o.assigned_to:
                    master = session.query(User).filter_by(tg_id=o.assigned_to).first()
                    if master:
                        master_name = master.full_name or master.name or f"ID {o.assigned_to}"
                        master_info = f"\n👤 Мастер: {master_name}"
                
                city_name = o.city_rel.name if o.city_rel else "Не указан"
                from handlers.utils import get_status_name_ru
                text = f"\n<b>Заявка #{o.order_number}</b>\n🏙 Город: {city_name}\n📍 Адрес: ул. {o.street}, дом {o.house}\n🔧 Тип: {equip_type_name}\n📊 Статус: {get_status_name_ru(o.status)}{master_info}\n"
                self.bot.send_message(message.chat.id, text)
            self.bot.send_message(message.chat.id, "✅ Готово!", reply_markup=main_keyboard(role))
        finally:
            session.close()
    
    def handle_stats(self, message: types.Message) -> None:
        """Показать статистику"""
        session = get_session()
        try:
            role = get_role(session, message.from_user.id)
            uid = message.from_user.id
            
            # Диспетчеры не видят статистику
            if role == "dispatcher":
                self.bot.reply_to(message, "🚫 У диспетчеров нет доступа к статистике.")
                return
            
            if role == "master":
                # Для мастера показываем только его статистику
                stats = session.query(Stat).filter_by(master_tg=uid).all()
                total = sum(x.sum for x in stats)
                by_type = {}
                cnt = {}
                for x in stats:
                    by_type[x.equip_type] = by_type.get(x.equip_type, 0) + (x.sum or 0)
                    cnt[x.equip_type] = cnt.get(x.equip_type, 0) + (0 if x.refused else 1)
                text = f"📊 Ваша статистика:\nВсего заявок: {len(stats)}\nЗаработано: {total:.2f} руб.\n"
                for k, v in by_type.items():
                    avg = v / cnt.get(k, 1) if cnt.get(k, 0) > 0 else 0
                    # Получаем название типа техники по коду
                    equip_type_name = get_equip_type_name(k)
                    text += f"- {equip_type_name}: средний чек {avg:.2f} руб.\n"
            else:
                # Для остальных ролей - общая статистика
                stats = session.query(Stat).all()
                total = sum(x.sum for x in stats)
                by_type = {}
                cnt = {}
                for x in stats:
                    by_type[x.equip_type] = by_type.get(x.equip_type, 0) + (x.sum or 0)
                    cnt[x.equip_type] = cnt.get(x.equip_type, 0) + (0 if x.refused else 1)
                text = f"📊 Общая статистика:\nВсего операций: {len(stats)}\nВаловая касса: {total:.2f} руб.\n"
                for k, v in by_type.items():
                    avg = v / cnt.get(k, 1) if cnt.get(k, 0) > 0 else 0
                    # Получаем название типа техники по коду
                    equip_type_name = get_equip_type_name(k)
                    text += f"- {equip_type_name}: средний чек {avg:.2f} руб.\n"
            
            self.bot.send_message(message.chat.id, text, reply_markup=main_keyboard(role))
        finally:
            session.close()
    
    def handle_manage_masters(self, message: types.Message) -> None:
        """Управление мастерами для диспетчеров"""
        session = get_session()
        try:
            role = get_role(session, message.from_user.id)
            if role != "dispatcher":
                self.bot.reply_to(message, "🚫 Только диспетчеры могут управлять мастерами.")
                return
            
            # Показываем список мастеров с возможностью назначения заявок
            masters = session.query(User).filter_by(role="master").all()
            if not masters:
                self.bot.send_message(message.chat.id, "👥 Мастеров пока нет в системе.", reply_markup=main_keyboard(role))
                return
            
            text = "👥 <b>Управление мастерами:</b>\n\n"
            for i, master in enumerate(masters, 1):
                # Считаем активные заявки мастера
                active_orders = session.query(Order).filter(
                    Order.assigned_to == master.tg_id,
                    Order.status.in_(["accepted", "on_place"])
                ).count()
                
                text += f"{i}. <b>{master.name}</b> (ID: {master.tg_id})\n"
                text += f"   📋 Активных заявок: {active_orders}\n\n"
            
            text += "💡 <i>Для назначения заявки мастеру используйте команду /assign</i>"
            self.bot.send_message(message.chat.id, text, reply_markup=main_keyboard(role), parse_mode="HTML")
        finally:
            session.close()


class MasterHandler(RoleHandler):
    """Обработчик для мастеров"""
    
    def handle_my_sd(self, message: types.Message) -> None:
        """Показать технику на руках у мастера (СД)"""
        session = get_session()
        try:
            role = get_role(session, message.from_user.id)
            if role != "master":
                self.bot.reply_to(message, "Нет доступа.")
                return
            
            # Техника на руках у мастера (активные заявки)
            active_orders = session.query(Order).filter(
                Order.assigned_to == message.from_user.id,
                Order.status.in_(["accepted", "on_place"])
            ).all()
            
            if not active_orders:
                text = "📦 У вас нет техники на руках (СД) 🛠️"
            else:
                text = "📦 Техника на руках:\n\n"
                for order in active_orders:
                    # Получаем название типа техники по коду
                    equip_type_name = get_equip_type_name(order.equip_type)
                    from handlers.utils import get_status_name_ru
                    text += f"#{order.order_number} - {equip_type_name}\n"
                    text += f"Адрес: {order.street}, д.{order.house}\n"
                    text += f"Статус: {get_status_name_ru(order.status)}\n\n"
            
            self.bot.send_message(message.chat.id, text, reply_markup=main_keyboard(role))
        finally:
            session.close()
    
    def handle_cash(self, message: types.Message) -> None:
        """Показать кассу мастера"""
        session = get_session()
        try:
            role = get_role(session, message.from_user.id)
            if role != "master":
                self.bot.reply_to(message, "Нет доступа.")
                return
            
            # Заявки с не сданной кассой
            pending_cash = session.query(Order).filter(
                Order.assigned_to == message.from_user.id,
                Order.status == "done_pending_sum"
            ).all()
            
            if not pending_cash:
                text = "💰 Все заявки по кассе сданы ✅"
                self.bot.send_message(message.chat.id, text, reply_markup=main_keyboard(role))
            else:
                text = "💰 Заявки готовые к закрытию (не сданы в кассу):\n\n"
                for order in pending_cash:
                    text += f"📋 <b>Заявка #{order.order_number}</b>\n"
                    text += f"💰 Сумма: {order.sum_amount or 0:.2f} руб.\n"
                    text += f"📄 Цена СД: {order.sd_price or 0:.2f} руб.\n"
                    text += f"🔧 ЗПЧ: {getattr(order, 'zpch_sum', 0):.2f} руб.\n"
                    text += f"📅 Дата: {order.created_at.date()}\n"
                    text += f"🏙 Город: {order.city_rel.name if order.city_rel else 'Не указан'}\n"
                    text += f"📍 Адрес: ул. {order.street}, д. {order.house}, кв. {order.flat}\n"
                    text += f"👤 Клиент: {order.client_name or 'Не указан'}\n"
                    text += f"📱 Телефон: {order.client_phone or 'Не указан'}\n"
                    
                    if order.receipt_file_id:
                        text += f"📎 Чек прикреплен\n"
                    
                    text += f"\n⚠️ Нажмите 'Закрыть заявку' для сдачи в кассу\n\n"
                
                # Добавляем кнопки для просмотра чеков
                kb = types.InlineKeyboardMarkup()
                for order in pending_cash:
                    if order.receipt_file_id:
                        kb.add(types.InlineKeyboardButton(
                            f"📎 Посмотреть чек #{order.order_number}", 
                            callback_data=f"view_receipt:{order.id}"
                        ))
                
                if kb.keyboard:
                    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_main"))
                    self.bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode="HTML")
                else:
                    self.bot.send_message(message.chat.id, text, reply_markup=main_keyboard(role), parse_mode="HTML")
        finally:
            session.close()
    
    def handle_view_receipt(self, callback: types.CallbackQuery) -> None:
        """Показать фото чека"""
        session = get_session()
        try:
            user_id = callback.from_user.id
            order_id = int(callback.data.split(":")[1])
            
            # Проверяем, что заявка принадлежит мастеру
            order = session.query(Order).filter_by(id=order_id, assigned_to=user_id).first()
            if not order:
                self.bot.answer_callback_query(callback.id, "Нет доступа к заявке")
                return
            
            if not order.receipt_file_id:
                self.bot.answer_callback_query(callback.id, "Чек не прикреплен")
                return
            
            # Отправляем фото чека
            self.bot.send_photo(
                callback.message.chat.id,
                order.receipt_file_id,
                caption=f"📎 Чек по заявке #{order.order_number}\n"
                       f"💰 Сумма: {order.sum_amount or 0:.2f} руб.\n"
                       f"📄 Цена СД: {order.sd_price or 0:.2f} руб.\n"
                       f"📅 Дата: {order.created_at.date()}"
            )
            
            self.bot.answer_callback_query(callback.id, "Чек отправлен")
        finally:
            session.close()
    
    def handle_refresh(self, message: types.Message) -> None:
        """Обновить меню мастера"""
        session = get_session()
        try:
            role = get_role(session, message.from_user.id)
            if role != "master":
                self.bot.reply_to(message, "Нет доступа.")
                return
            
            self.bot.send_message(message.chat.id, "🔄 Меню обновлено! ✨", reply_markup=main_keyboard(role))
        finally:
            session.close()


class DirectorHandler(RoleHandler):
    """Обработчик для директоров"""
    
    def handle_admin_panel(self, message: types.Message) -> None:
        """Показать админ-панель"""
        session = get_session()
        try:
            role = get_role(session, message.from_user.id)
            if role not in ("owner", "director"):
                self.bot.reply_to(message, "🚫 Нет доступа.")
                return
            kb = admin_keyboard(role)
            self.bot.send_message(message.chat.id, "⚙️ Админ-панель:", reply_markup=kb)
        finally:
            session.close()
    
    def handle_manage_masters_admin(self, message: types.Message) -> None:
        """Управление мастерами для директоров"""
        session = get_session()
        try:
            role = get_role(session, message.from_user.id)
            if role not in ("director", "owner"):
                self.bot.reply_to(message, "🚫 Только директор или собственник может управлять мастерами.")
                return
            
            # Показываем список мастеров и кнопку создания
            masters = session.query(User).filter_by(role="master").all()
            
            text = "👥 <b>Управление мастерами:</b>\n\n"
            if masters:
                for i, master in enumerate(masters, 1):
                    text += f"{i}. <b>{master.full_name or master.name}</b>\n"
                    text += f"   📱 {master.phone or 'Не указан'}\n"
                    city_name = master.city_rel.name if master.city_rel else "Не указан"
                    text += f"   🏙 {city_name}\n"
                    text += f"   🆔 ID: {master.tg_id}\n\n"
            else:
                text += "📭 Мастеров пока нет в системе.\n\n"
            
            text += "💡 <i>Используйте кнопки ниже для управления</i>"
            
            kb = create_master_keyboard()
            self.bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode="HTML")
        finally:
            session.close()
    
    def handle_add_master_director(self, message: types.Message) -> None:
        """Добавить мастера для директора"""
        session = get_session()
        try:
            role = get_role(session, message.from_user.id)
            if role not in ("director", "owner"):
                self.bot.reply_to(message, "🚫 Только директор или собственник может добавлять мастеров.")
                return
            
            # Показываем выбор способа создания мастера
            kb = master_creation_method_keyboard()
            self.bot.send_message(message.chat.id, "👤 <b>Создание нового мастера:</b>\n\nВыберите способ создания:", reply_markup=kb, parse_mode="HTML")
        finally:
            session.close()
    
    def handle_director_sd(self, message: types.Message) -> None:
        """Показать СД для директора"""
        session = get_session()
        try:
            role = get_role(session, message.from_user.id)
            if role != "director":
                self.bot.reply_to(message, "🚫 Только директор имеет доступ к СД.")
                return
            
            # Показываем все активные заявки (техника на руках у мастеров)
            active_orders = session.query(Order).filter(
                Order.status.in_(["accepted", "on_place"])
            ).all()
            
            if not active_orders:
                text = "📦 Нет техники на руках у мастеров (СД пусто) 🛠️"
            else:
                text = "📦 <b>Техника на руках у мастеров (СД):</b>\n\n"
                for order in active_orders:
                    # Получаем информацию о мастере
                    master = session.query(User).filter_by(tg_id=order.assigned_to).first()
                    master_name = master.full_name or master.name or f"ID {order.assigned_to}" if master else f"ID {order.assigned_to}"
                    
                    # Получаем название типа техники
                    equip_type_name = get_equip_type_name(order.equip_type)
                    
                    text += f"🔧 <b>#{order.order_number}</b> - {equip_type_name}\n"
                    text += f"   👤 Мастер: {master_name}\n"
                    text += f"   📍 Адрес: {order.street}, д.{order.house}\n"
                    text += f"   📅 Дата: {order.created_at.date()}\n"
                    text += f"   ⏰ Время: {order.time_from} - {order.time_to}\n"
                    text += f"   📝 Описание: {order.short_desc}\n\n"
            
            self.bot.send_message(message.chat.id, text, reply_markup=main_keyboard(role), parse_mode="HTML")
        finally:
            session.close()

    def handle_cash_overview(self, message: types.Message) -> None:
        """Показать кассу города (для owner/director)"""
        session = get_session()
        try:
            role = get_role(session, message.from_user.id)
            if role not in ("owner", "director"):
                self.bot.reply_to(message, "Нет доступа.")
                return
            city_id = None
            if role == "director":
                u = session.query(User).filter_by(tg_id=message.from_user.id).first()
                city_id = getattr(u, 'city_id', None)
            # Получаем выплаты после последней очистки
            cleared_at = user_states.get_cash_cleared_timestamp(city_id or 0)
            stats = session.query(Stat).all()
            total_company = 0.0
            lines = []
            for s in stats:
                # Берем заявки города (если задан)
                order = session.query(Order).filter_by(id=s.order_id).first()
                if city_id is not None and getattr(order, 'city_id', None) != city_id:
                    continue
                
                # Фильтрация по времени последней очистки кассы
                if cleared_at and order.created_at < cleared_at:
                    continue
                
                # Сумма к сдаче приблизительно company_pct из services
                from services.equipment_service import get_pct
                m_pct, c_pct = get_pct(s.equip_type)
                company_sum = s.sum * (c_pct / 100.0)
                total_company += company_sum
                lines.append(f"#{getattr(order,'order_number','-')}: {company_sum:.2f}")
            text = "💼 <b>Касса</b>\n" + "\n".join(lines[-20:]) + f"\n\nИтого: {total_company:.2f}"
            kb = types.InlineKeyboardMarkup()
            if role in ("owner", "director"):
                kb.add(types.InlineKeyboardButton("🧹 Очистить кассу", callback_data="cash_clear"))
            self.bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode="HTML")
        finally:
            session.close()

    def handle_cash_clear(self, callback: types.CallbackQuery) -> None:
        """Очистить кассу для города (director своего города, owner любой)"""
        session = get_session()
        try:
            role = get_role(session, callback.from_user.id)
            if role not in ("owner", "director"):
                self.bot.answer_callback_query(callback.id, "Нет доступа")
                return
            
            city_id = None
            city_name = "всех городов"
            if role == "director":
                u = session.query(User).filter_by(tg_id=callback.from_user.id).first()
                city_id = getattr(u, 'city_id', None)
                if city_id:
                    city = session.query(City).filter_by(id=city_id).first()
                    city_name = city.name if city else f"ID {city_id}"
            
            # Показываем подтверждение с информацией о том, что будет очищено
            from datetime import datetime
            current_time = datetime.now()
            
            # Считаем сумму, которая будет очищена
            cleared_at = user_states.get_cash_cleared_timestamp(city_id or 0)
            stats = session.query(Stat).all()
            total_to_clear = 0.0
            
            for s in stats:
                order = session.query(Order).filter_by(id=s.order_id).first()
                if not order:
                    continue
                    
                # Фильтрация по городу
                if city_id is not None and getattr(order, 'city_id', None) != city_id:
                    continue
                
                # Фильтрация по времени последней очистки
                if cleared_at and order.created_at < cleared_at:
                    continue
                
                from services.equipment_service import get_pct
                m_pct, c_pct = get_pct(s.equip_type)
                company_sum = s.sum * (c_pct / 100.0)
                total_to_clear += company_sum
            
            # Создаем клавиатуру подтверждения
            from handlers.menu_kb import cash_clear_confirm_keyboard
            kb = cash_clear_confirm_keyboard()
            
            confirm_text = f"🧹 <b>Подтверждение очистки кассы</b>\n\n"
            confirm_text += f"🏙 Город: {city_name}\n"
            confirm_text += f"💰 Сумма к очистке: {total_to_clear:.2f} руб.\n"
            confirm_text += f"⏰ Время: {current_time.strftime('%d.%m.%Y %H:%M')}\n\n"
            confirm_text += f"⚠️ <b>Внимание!</b> Это действие нельзя отменить.\n"
            confirm_text += f"Все заявки до этого времени будут исключены из кассы."
            
            self.bot.edit_message_text(
                confirm_text,
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                reply_markup=kb,
                parse_mode="HTML"
            )
            self.bot.answer_callback_query(callback.id, "Подтверждение очистки")
        finally:
            session.close()
    
    def handle_cash_clear_confirm(self, callback: types.CallbackQuery) -> None:
        """Подтвердить очистку кассы"""
        session = get_session()
        try:
            role = get_role(session, callback.from_user.id)
            if role not in ("owner", "director"):
                self.bot.answer_callback_query(callback.id, "Нет доступа")
                return
            
            city_id = None
            city_name = "всех городов"
            if role == "director":
                u = session.query(User).filter_by(tg_id=callback.from_user.id).first()
                city_id = getattr(u, 'city_id', None)
                if city_id:
                    city = session.query(City).filter_by(id=city_id).first()
                    city_name = city.name if city else f"ID {city_id}"
            
            # Выполняем очистку
            from datetime import datetime
            user_states.set_cash_cleared_timestamp(city_id or 0, datetime.now())
            
            success_text = f"✅ <b>Касса успешно очищена!</b>\n\n"
            success_text += f"🏙 Город: {city_name}\n"
            success_text += f"⏰ Время очистки: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            success_text += f"💡 Теперь в кассе будут отображаться только новые заявки."
            
            self.bot.edit_message_text(
                success_text,
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                parse_mode="HTML"
            )
            self.bot.answer_callback_query(callback.id, "Касса очищена!")
        finally:
            session.close()


class OwnerHandler(RoleHandler):
    """Обработчик для собственников"""
    
    def handle_city_management(self, callback: types.CallbackQuery) -> None:
        """Управление городами"""
        session = get_session()
        try:
            role = get_role(session, callback.from_user.id)
            if role != "owner":
                self.bot.answer_callback_query(callback.id, "Нет доступа")
                return
            
            from handlers.menu_kb import city_management_keyboard
            kb = city_management_keyboard()
            self.bot.edit_message_text(
                "🏙 <b>Управление городами:</b>", 
                chat_id=callback.message.chat.id, 
                message_id=callback.message.message_id, 
                reply_markup=kb, 
                parse_mode="HTML"
            )
        finally:
            session.close()
    
    def handle_list_cities(self, callback: types.CallbackQuery) -> None:
        """Показать список городов"""
        session = get_session()
        try:
            msg = self._city_list_message(session)
            kb = admin_back_keyboard()
            self.bot.edit_message_text(
                msg, 
                chat_id=callback.message.chat.id, 
                message_id=callback.message.message_id, 
                reply_markup=kb, 
                parse_mode="HTML"
            )
        finally:
            session.close()
    
    def handle_add_city(self, callback: types.CallbackQuery) -> None:
        """Добавить город"""
        session = get_session()
        try:
            role = get_role(session, callback.from_user.id)
            if role != "owner":
                self.bot.answer_callback_query(callback.id, "Нет доступа")
                return
            
            self.states.set_city_management_state(callback.from_user.id, "add")
            self.bot.edit_message_text(
                "Введите название нового города:", 
                chat_id=callback.message.chat.id, 
                message_id=callback.message.message_id
            )
            self.bot.answer_callback_query(callback.id, "Название?")
        finally:
            session.close()
    
    def handle_delete_city(self, callback: types.CallbackQuery) -> None:
        """Удалить город"""
        session = get_session()
        try:
            role = get_role(session, callback.from_user.id)
            if role != "owner":
                self.bot.answer_callback_query(callback.id, "Нет доступа")
                return
            
            cities = session.query(City).all()
            if not cities:
                self.bot.edit_message_text(
                    "❌ Городов еще нет.", 
                    chat_id=callback.message.chat.id, 
                    message_id=callback.message.message_id
                )
                return
            
            kb = types.InlineKeyboardMarkup()
            for city in cities:
                kb.add(types.InlineKeyboardButton(f"{city.name}", callback_data=f"confirm_del_city:{city.id}"))
            kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin_cities"))
            self.bot.edit_message_text(
                "🗑 Выберите город для удаления:", 
                chat_id=callback.message.chat.id, 
                message_id=callback.message.message_id, 
                reply_markup=kb
            )
        finally:
            session.close()
    
    def handle_confirm_del_city(self, callback: types.CallbackQuery) -> None:
        """Подтвердить удаление города"""
        session = get_session()
        try:
            city_id = int(callback.data.split(":")[1])
            city = session.query(City).filter_by(id=city_id).first()
            if not city:
                self.bot.answer_callback_query(callback.id, "Не найден!")
                return
            
            # не даём удалить если есть пользователи или заявки
            users = session.query(User).filter_by(city_id=city_id).count()
            orders = session.query(Order).filter_by(city_id=city_id).count()
            if users or orders:
                self.bot.answer_callback_query(callback.id, f"Есть связанные пользователи/заявки")
                return
            
            session.delete(city)
            session.commit()
            msg = self._city_list_message(session) + "\n\n✅ Удалено"
            from handlers.menu_kb import city_management_keyboard
            kb = city_management_keyboard()
            self.bot.edit_message_text(
                msg, 
                chat_id=callback.message.chat.id, 
                message_id=callback.message.message_id, 
                reply_markup=kb, 
                parse_mode="HTML"
            )
            self.bot.answer_callback_query(callback.id, "Удалено!")
        finally:
            session.close()
    
    def handle_city_add_name(self, message: types.Message) -> None:
        """Обработать ввод названия города"""
        session = get_session()
        try:
            city_name = message.text.strip()
            if not city_name:
                self.bot.send_message(message.chat.id, '❌ Название не может быть пустым!')
                return
            
            if session.query(City).filter_by(name=city_name).first():
                self.bot.send_message(message.chat.id, '❌ Такой город уже есть!')
                return
            
            session.add(City(name=city_name))
            session.commit()
            msg = self._city_list_message(session) + "\n\n✅ Город добавлен"
            from handlers.menu_kb import city_management_keyboard
            kb = city_management_keyboard()
            self.bot.send_message(message.chat.id, msg, reply_markup=kb, parse_mode="HTML")
            self.states.clear_city_management_state(message.from_user.id)
        finally:
            session.close()
    
    def _city_list_message(self, session) -> str:
        """Сформировать сообщение со списком городов"""
        cities = session.query(City).all()
        if not cities:
            return '❌ Города не заданы'
        msg = '🏙 <b>Текущие города:</b>\n'
        for i, c in enumerate(cities, 1):
            msg += f"{i}. <b>{c.name}</b> [ID: {c.id}]\n"
        return msg
    
    def handle_equipment_percentages(self, callback: types.CallbackQuery) -> None:
        """Обработать управление процентами типов техники"""
        session = get_session()
        try:
            user_id = callback.from_user.id
            role = get_role(session, user_id)
            
            if role != "owner":
                self.bot.answer_callback_query(callback.id, "Нет доступа")
                return
            
            from services.equipment_service import EQUIP_SETTINGS
            from handlers.menu_kb import equipment_percentages_keyboard
            
            kb = equipment_percentages_keyboard(EQUIP_SETTINGS)
            self.bot.edit_message_text(
                "⚙️ <b>Управление процентами типов техники:</b>",
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                reply_markup=kb,
                parse_mode="HTML"
            )
            self.bot.answer_callback_query(callback.id, "Управление процентами")
        finally:
            session.close()
    
    def handle_edit_equipment_percentage(self, callback: types.CallbackQuery) -> None:
        """Обработать редактирование процента типа техники"""
        session = get_session()
        try:
            user_id = callback.from_user.id
            role = get_role(session, user_id)
            
            if role != "owner":
                self.bot.answer_callback_query(callback.id, "Нет доступа")
                return
            
            equip_type = callback.data.split(":")[1]
            self.states.set_equipment_edit_state(user_id, {"equip_type": equip_type, "step": "master_pct"})
            
            from services.equipment_service import EQUIP_SETTINGS
            current_pct = EQUIP_SETTINGS.get(equip_type, {}).get('master_pct', 60)
            
            kb = self._get_cancel_edit_keyboard()
            self.bot.send_message(
                callback.message.chat.id,
                f"🔧 <b>Редактирование процента для {EQUIP_SETTINGS.get(equip_type, {}).get('name', equip_type)}</b>\n\n"
                f"Текущий процент мастера: {current_pct}%\n\n"
                f"Введите новый процент мастера (0-100):",
                reply_markup=kb,
                parse_mode="HTML"
            )
            self.bot.answer_callback_query(callback.id, "Редактирование процента")
        finally:
            session.close()
    
    def handle_equipment_percentage_input(self, message: types.Message) -> None:
        """Обработать ввод процента мастера"""
        session = get_session()
        try:
            user_id = message.from_user.id
            state = self.states.get_equipment_edit_state(user_id)
            if not state:
                return
            
            try:
                percentage = float(message.text.strip())
                if not 0 <= percentage <= 100:
                    self.bot.send_message(message.chat.id, "❌ Процент должен быть от 0 до 100")
                    return
                
                equip_type = state["equip_type"]
                
                # Обновляем процент в сервисе
                from services.equipment_service import update_equipment_percentage
                update_equipment_percentage(equip_type, percentage)
                
                # Обновляем в БД если есть запись
                from model import EquipmentType
                equip_type_record = session.query(EquipmentType).filter_by(name=equip_type).first()
                if equip_type_record:
                    equip_type_record.master_pct = percentage
                    equip_type_record.company_pct = 100 - percentage
                    session.commit()
                
                self.bot.send_message(
                    message.chat.id,
                    f"✅ Процент мастера для {equip_type} обновлен: {percentage}%"
                )
                
                self.states.clear_equipment_edit_state(user_id)
                
            except ValueError:
                self.bot.send_message(message.chat.id, "❌ Введите корректное число")
        finally:
            session.close()
    
    def _get_cancel_edit_keyboard(self):
        """Получить клавиатуру отмены редактирования"""
        # Кнопки отмены отключены по требованию
        return None
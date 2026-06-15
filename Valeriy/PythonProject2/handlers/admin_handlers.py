import logging
from telebot import types
from db import get_session
from services.user_service import get_role, require_role, get_available_roles_for_role, is_dispatcher_hidden_from_role
from handlers.menu_kb import role_selection_keyboard
from model import User

logger = logging.getLogger(__name__)

def register(bot):
    # Обработчики callback для админ-панели
    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_"))
    def admin_callbacks(c: types.CallbackQuery):
        session = get_session()
        user_role = get_role(session, c.from_user.id)
        
        # Панель директора
        if c.data == "admin_orders":
            if user_role != "director":
                bot.answer_callback_query(c.id, "Нет доступа")
                session.close(); return
            
            # Не назначенные заявки мастерам
            from model import Order
            unassigned = session.query(Order).filter(Order.assigned_to.is_(None)).all()
            if unassigned:
                text = "📋 Не назначенные заявки:\n\n"
                for order in unassigned:
                    city_name = order.city_rel.name if order.city_rel else "Не указан"
                    text += f"#{order.order_number} - {city_name}, {order.equip_type}\n"
                    text += f"Адрес: {order.street}, д.{order.house}\n"
                    text += f"Время: {order.time_from}-{order.time_to}\n\n"
            else:
                text = "✅ Все заявки назначены мастерам"
            
            bot.edit_message_text(text, chat_id=c.message.chat.id, message_id=c.message.message_id)
            session.close(); return

        if c.data == "admin_stats":
            if user_role != "director":
                bot.answer_callback_query(c.id, "Нет доступа")
                session.close(); return
            
            # Статистика с выгрузкой
            from model import Stat
            stats = session.query(Stat).all()
            total = sum(x.sum for x in stats)
            text = f"📊 Статистика:\n\nВсего операций: {len(stats)}\nВаловая касса: {total:.2f} руб.\n\n"
            text += "Для выгрузки данных используйте команду /export"
            
            bot.edit_message_text(text, chat_id=c.message.chat.id, message_id=c.message.message_id)
            session.close(); return

        if c.data == "admin_cashier":
            if user_role != "director":
                bot.answer_callback_query(c.id, "Нет доступа")
                session.close(); return
            
            # Просмотр не принятых заявок по кассе от мастеров
            from model import Order
            pending_orders = session.query(Order).filter(Order.status == "done_pending_sum").all()
            if pending_orders:
                text = "💰 Не принятые заявки по кассе:\n\n"
                for order in pending_orders:
                    master = session.query(User).filter_by(tg_id=order.assigned_to).first()
                    master_name = master.name if master else "Неизвестно"
                    text += f"#{order.order_number} ({master_name})\n"
                    text += f"Сумма: {order.sum_amount or 'Не указана'} руб.\n\n"
            else:
                text = "✅ Все заявки по кассе обработаны"
            
            bot.edit_message_text(text, chat_id=c.message.chat.id, message_id=c.message.message_id)
            session.close(); return

        if c.data == "admin_warehouse":
            if user_role != "director":
                bot.answer_callback_query(c.id, "Нет доступа")
                session.close(); return
            
            # Техника которая находится на руках у мастеров
            from model import Order
            active_orders = session.query(Order).filter(Order.status.in_(["accepted", "on_place"])).all()
            if active_orders:
                text = "🔧 Техника у мастеров:\n\n"
                masters_equipment = {}
                for order in active_orders:
                    master = session.query(User).filter_by(tg_id=order.assigned_to).first()
                    if master:
                        master_name = master.name
                        if master_name not in masters_equipment:
                            masters_equipment[master_name] = []
                        masters_equipment[master_name].append(order)
                
                for master_name, orders in masters_equipment.items():
                    text += f"👨‍🔧 {master_name} ({len(orders)} техники):\n"
                    for order in orders:
                        text += f"  #{order.order_number} - {order.equip_type}\n"
                    text += "\n"
            else:
                text = "✅ Нет техники на руках у мастеров"
            
            bot.edit_message_text(text, chat_id=c.message.chat.id, message_id=c.message.message_id)
            session.close(); return

        # Панель собственника
        if c.data == "admin_masters":
            if user_role != "owner":
                bot.answer_callback_query(c.id, "Нет доступа")
                session.close(); return
            
            masters = session.query(User).filter_by(role="master").all()
            text = "Мастера:\n" + "\n".join([f"{m.name} — {m.tg_id}" for m in masters]) if masters else "Мастеров нет"
            bot.edit_message_text(text, chat_id=c.message.chat.id, message_id=c.message.message_id)
            session.close(); return

        if c.data == "admin_dispatchers":
            if user_role != "owner":
                bot.answer_callback_query(c.id, "Только собственник")
                session.close(); return
            
            dispatchers = session.query(User).filter_by(role="dispatcher").all()
            text = "Диспетчеры:\n" + "\n".join([f"{d.name} — {d.tg_id}" for d in dispatchers]) if dispatchers else "Диспетчеров нет"
            bot.edit_message_text(text, chat_id=c.message.chat.id, message_id=c.message.message_id)
            session.close(); return

        if c.data == "admin_users":
            if user_role != "owner":
                bot.answer_callback_query(c.id, "Нет доступа")
                session.close(); return
            
            # Показать пользователей с возможностью назначения ролей
            kb = role_selection_keyboard(user_role)
            bot.edit_message_text("Выберите роль для назначения:", chat_id=c.message.chat.id, message_id=c.message.message_id, reply_markup=kb)
            session.close(); return

        if c.data == "admin_types":
            if user_role != "owner":
                bot.answer_callback_query(c.id, "Нет доступа")
                session.close(); return
            
            bot.edit_message_text("Управление типами техники (в разработке)", chat_id=c.message.chat.id, message_id=c.message.message_id)
            session.close(); return

        bot.answer_callback_query(c.id, "Неизвестная команда")
        session.close()

    # Обработчик назначения ролей через callback
    @bot.callback_query_handler(func=lambda c: c.data.startswith("set_role:"))
    def set_role_callback(c: types.CallbackQuery):
        session = get_session()
        user_role = get_role(session, c.from_user.id)
        
        if not require_role(session, c.from_user.id, ("owner", "director")):
            bot.answer_callback_query(c.id, "Нет доступа")
            session.close(); return
        
        target_role = c.data.split(":")[1]
        available_roles = get_available_roles_for_role(user_role)
        
        if target_role not in available_roles:
            bot.answer_callback_query(c.id, "Недоступная роль")
            session.close(); return
        
        # Сохраняем выбранную роль для следующего шага
        bot.edit_message_text(f"Выбрана роль: {target_role}\nВведите Telegram ID пользователя:", chat_id=c.message.chat.id, message_id=c.message.message_id)
        
        # Устанавливаем состояние ожидания ввода ID
        # Можно использовать FORM_STATE или создать отдельный механизм
        bot.answer_callback_query(c.id, f"Теперь введите ID пользователя для роли {target_role}")
        session.close()

    # Обработчик ввода ID пользователя для назначения роли
    @bot.message_handler(func=lambda m: True)  # Временный обработчик, нужно улучшить логику состояний
    def handle_user_id_input(m: types.Message):
        # Здесь должна быть логика обработки ввода ID пользователя
        # и назначения роли через команду /setrole
        pass

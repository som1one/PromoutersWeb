"""
Обработчики для работы с заявками.
Содержит логику создания, подтверждения и управления заявками.
"""

import logging
from typing import Dict, Any
from telebot import types
from db import get_session
from services.user_service import get_role, generate_order_number
from handlers.utils import get_equip_type_name
from handlers.menu_kb import (
    main_keyboard, master_new_order_kb, master_way_kb, master_ready_kb,
    order_sum_keyboard, zpch_sum_keyboard, receipt_keyboard, close_order_keyboard
)
from model import User, Order, Stat
from _vk.state_manager import user_states

logger = logging.getLogger(__name__)


class OrderHandler:
    """Класс для обработки заявок"""
    
    def __init__(self, bot):
        self.bot = bot
        self.states = user_states
    
    def confirm_order_callback(self, callback: types.CallbackQuery) -> None:
        """Подтвердить создание заявки"""
        session = get_session()
        try:
            user_id = callback.from_user.id
            state = self.states.get_form_state(user_id)
            if not state or state["step"] != "confirm":
                self.bot.answer_callback_query(callback.id, "Нет данных для подтверждения")
                return
            
            order_data = state["order_data"]
            
            # Создаем заявку в БД
            order = Order(
                order_number=order_data["order_number"],
                city_id=order_data["city_id"],
                street=order_data["street"],
                house=order_data["house"],
                flat=order_data["flat"],
                time_from=order_data["time_from"],
                time_to=order_data["time_to"],
                # order_date=order_data.get("order_date"),  # временно закомментировано
                equip_type=order_data.get("equip_type_code", order_data["equip_type"]),
                short_desc=order_data["short_desc"],
                source=order_data["source"],
                created_by=user_id,
                assigned_to=order_data.get("assigned_to"),
                client_name=order_data.get("client_name"),
                client_phone=order_data.get("client_phone"),
                comment=order_data.get("comment", ""),
                is_warranty=bool(order_data.get("is_warranty", False)),
            )
            session.add(order)
            session.commit()
            
            # Проверяем, нужно ли планировать заявку на будущую дату
            from datetime import datetime, date
            today = date.today()
            order_date = order_data.get("order_date")
            
            if order_date and order_date > today:
                # Заявка на будущую дату - планируем её
                from services.scheduler_service import SchedulerService
                scheduler = SchedulerService(self.bot)
                scheduler.schedule_order_for_date(order, datetime.combine(order_date, datetime.min.time()))
            else:
                # Заявка на сегодня - уведомляем мастера сразу
                if order.assigned_to:
                    self._notify_master(order, session)
            
            # Уведомляем директоров и собственников
            self._notify_admins(order, session)
            
            # Уведомляем управляющих
            self._notify_managers(order, session)
            
            if order.assigned_to:
                master_name = order_data.get("master_name", "мастеру")
                self.bot.edit_message_text(
                    f"✅ Заявка #{order.order_number} создана и отправлена {master_name}! 🎉", 
                    chat_id=callback.message.chat.id, 
                    message_id=callback.message.message_id
                )
            else:
                self.bot.edit_message_text(
                    f"✅ Заявка #{order.order_number} создана! 🎉", 
                    chat_id=callback.message.chat.id, 
                    message_id=callback.message.message_id
                )
            
            role = get_role(session, user_id)
            kb = main_keyboard(role)
            self.bot.send_message(callback.message.chat.id, "🏠 Главное меню:", reply_markup=kb)
            self.bot.answer_callback_query(callback.id, "Заявка создана!")
            
            self.states.clear_form_state(user_id)
        finally:
            session.close()
    
    def _notify_master(self, order: Order, session) -> None:
        """Уведомить мастера о новой заявке"""
        try:
            master = session.query(User).filter_by(tg_id=order.assigned_to).first()
            if master:
                kb = master_new_order_kb(order.id)
                # Показываем только основную информацию, без деталей заявки
                message_text = f"🎯 <b>Вам назначена новая заявка №{order.order_number}</b>\n\n"
                message_text += f"🏙 Город: {order.city_rel.name if order.city_rel else 'Не указан'}\n"
                message_text += f"⏰ Время: {order.time_from} - {order.time_to}\n"
                message_text += f"🔧 Тип техники: {get_equip_type_name(order.equip_type)}\n\n"
                message_text += f"<i>Нажмите 'Принять' для просмотра полной информации о заявке</i>"
                self.bot.send_message(order.assigned_to, message_text, reply_markup=kb, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Failed to notify master {order.assigned_to}: {e}")
    
    def _notify_admins(self, order: Order, session) -> None:
        """Уведомить администраторов о назначении заявки"""
        admins = session.query(User).filter(User.role.in_(["director", "owner"])).all()
        for admin in admins:
            try:
                master = session.query(User).filter_by(tg_id=order.assigned_to).first()
                master_name = master.name if master else f"ID {order.assigned_to}"
                message_text = f"📋 <b>Заявка #{order.order_number} назначена мастеру</b>\n\n"
                message_text += f"🔧 Мастер: {master_name}\n"
                city_name = order.city_rel.name if order.city_rel else "Не указан"
                message_text += f"🏙 Город: {city_name}\n"
                message_text += f"📍 Адрес: {order.street}, д. {order.house}, кв. {order.flat}\n"
                message_text += f"🔧 Техника: {get_equip_type_name(order.equip_type)}\n"
                message_text += f"📝 Описание: {order.short_desc}\n"
                self.bot.send_message(admin.tg_id, message_text, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"Failed to notify admin {admin.tg_id}: {e}")
    
    def _notify_managers(self, order: Order, session) -> None:
        """Уведомить управляющих о новой заявке"""
        managers = session.query(User).filter_by(role="manager").all()
        for mg in managers:
            try:
                self.bot.send_message(mg.tg_id, f"Новая заявка для назначения:\n\n{self._render_order(order)}")
            except Exception as e:
                logger.warning("notify manager failed %s", e)
    
    def _render_order(self, order: Order) -> str:
        """Отформатировать заявку для отображения"""
        equip_type_name = get_equip_type_name(order.equip_type)
        
        text = (
            f"📋 <b>Номер Заказа: {order.order_number}</b>\n"
            f"🏙 Город: {order.city_rel.name if order.city_rel else 'Не указан'}\n"
            f"📅 Дата заказа: {order.created_at.date()}\n"
            f"⏰ Время заказа: {order.time_from} - {order.time_to}\n"
            f"📍 Адрес заказа:\n"
            f"   - Ул.: {order.street}\n"
            f"   - Дом: {order.house}\n"
            f"   - Кв.: {order.flat}\n"
        )
        if order.client_name:
            text += f"👤 Ф.И.О: {order.client_name}\n"
        text += f"🔧 Техника: {equip_type_name}\n"
        text += f"📝 Описание заказа: {order.short_desc}\n"
        if order.comment:
            text += f"💬 {order.comment}\n"
        return text
    
    def handle_master_accept_callback(self, callback: types.CallbackQuery) -> None:
        """Обработать принятие заявки мастером"""
        session = get_session()
        try:
            uid = callback.from_user.id
            order_id = int(callback.data.split(":")[1])
            order = session.query(Order).filter_by(id=order_id).first()
            if order and order.assigned_to == uid:
                order.status = "accepted"
                session.commit()
                city_name = order.city_rel.name if getattr(order, 'city_rel', None) else None
                kb = master_way_kb(order.id, order.street, order.house, city_name)
                # Теперь показываем полную информацию о заявке
                self.bot.edit_message_text(
                    f"✅ Статус: Принято!\n\n{self._render_order(order)}\n\nОтметьте, когда будете выезжать. 🚗", 
                    chat_id=callback.message.chat.id, 
                    message_id=callback.message.message_id, 
                    reply_markup=kb
                )
                self.bot.answer_callback_query(callback.id, "Вы приняли заявку! 🎉")
            else:
                self.bot.answer_callback_query(callback.id, "Нет доступа или заявка не ваша")
        finally:
            session.close()
    
    def handle_master_on_way_callback(self, callback: types.CallbackQuery) -> None:
        """Обработать статус 'в пути' мастера"""
        session = get_session()
        try:
            uid = callback.from_user.id
            order_id = int(callback.data.split(":")[1])
            order = session.query(Order).filter_by(id=order_id).first()
            if order and order.assigned_to == uid:
                order.status = "on_place"
                session.commit()
                kb = master_ready_kb(order.id)
                self.bot.edit_message_text(
                    f"🚗 Статус: В пути!\n\n{self._render_order(order)}\n\nКак будете готовы - отмечайте 'Готово'! ⚡", 
                    chat_id=callback.message.chat.id, 
                    message_id=callback.message.message_id, 
                    reply_markup=kb
                )
                self.bot.answer_callback_query(callback.id, "Статус изменён на 'в пути' 🚗")
            else:
                self.bot.answer_callback_query(callback.id, "Нет доступа или заявка не ваша")
        finally:
            session.close()
    
    def handle_master_ready_callback(self, callback: types.CallbackQuery) -> None:
        """Обработать статус 'готово' мастера"""
        session = get_session()
        try:
            uid = callback.from_user.id
            order_id = int(callback.data.split(":")[1])
            order = session.query(Order).filter_by(id=order_id).first()
            if order and order.assigned_to == uid:
                order.status = "done_pending_sum"
                session.commit()
                
                # Инициализируем состояние ввода суммы
                self.states.set_sum_input_state(uid, {
                    "order_id": order_id,
                    "step": "order_sum",
                    "data": {}
                })
                
                kb = order_sum_keyboard()
                self.bot.edit_message_text(
                    "💰 <b>После нажатия на готово:</b>\n\nВведите сумму заказа (с учетом предоплаты долга):", 
                    chat_id=callback.message.chat.id, 
                    message_id=callback.message.message_id, 
                    reply_markup=kb, 
                    parse_mode="HTML"
                )
                self.bot.answer_callback_query(callback.id, "Введите сумму заказа 💰")
            else:
                self.bot.answer_callback_query(callback.id, "Нет доступа или заявка не ваша")
        finally:
            session.close()
    
    def handle_sum_input(self, message: types.Message) -> None:
        """Обработать ввод суммы"""
        user_id = message.from_user.id
        state = self.states.get_sum_input_state(user_id)
        if not state:
            return
        
        step = state["step"]
        text = message.text.strip()
        session = get_session()
        
        try:
            if step == "order_sum":
                # Ввод суммы заказа
                order_sum = float(text)
                state["data"]["order_sum"] = order_sum
                state["step"] = "zpch_sum"
                
                kb = zpch_sum_keyboard()
                self.bot.send_message(
                    message.chat.id, 
                    f"✅ Сумма заказа: {order_sum:.2f} руб.\n\n💰 Введите сумму ЗПЧ:", 
                    reply_markup=kb
                )
                
            elif step == "zpch_sum":
                # Ввод суммы ЗПЧ
                zpch_sum = float(text)
                state["data"]["zpch_sum"] = zpch_sum
                state["step"] = "sd_price"
                
                kb = sd_price_keyboard()
                self.bot.send_message(
                    message.chat.id, 
                    f"✅ Сумма ЗПЧ: {zpch_sum:.2f} руб.\n\n📄 Введите цену сервисного документа (СД):", 
                    reply_markup=kb
                )
                
            elif step == "sd_price":
                # Ввод цены СД
                sd_price = float(text)
                state["data"]["sd_price"] = sd_price
                
                if state["data"].get("zpch_sum", 0) > 0:
                    state["step"] = "receipt"
                    kb = receipt_keyboard()
                    self.bot.send_message(
                        message.chat.id, 
                        f"✅ Цена СД: {sd_price:.2f} руб.\n\n📎 Прикрепите чек на ЗПЧ:", 
                        reply_markup=kb
                    )
                else:
                    # Если ЗПЧ = 0, переходим к расчету
                    self._calculate_and_show_result(message, user_id, session)
                    
        except ValueError:
            self.bot.send_message(message.chat.id, "❌ Введите корректную сумму (число)")
        finally:
            session.close()
    
    def _calculate_and_show_result(self, message: types.Message, user_id: int, session) -> None:
        """Рассчитать и показать итоговую сумму"""
        state = self.states.get_sum_input_state(user_id)
        if not state:
            return
        
        order_id = state["order_id"]
        order_sum = state["data"].get("order_sum", 0)
        zpch_sum = state["data"].get("zpch_sum", 0)
        sd_price = state["data"].get("sd_price", 0)
        
        # Получаем заявку из БД
        order = session.query(Order).filter_by(id=order_id).first()
        if not order:
            self.bot.send_message(message.chat.id, "❌ Заявка не найдена")
            return
        
        # Рассчитываем по новой сетке процентов от чистого чека (order_sum - sd_price - zpch_sum)
        net_amount = max(order_sum - sd_price - zpch_sum, 0)
        try:
            from services.commission_service import get_master_pct
            master_pct = get_master_pct(order.equip_type, net_amount)
        except Exception:
            master_pct = 40.0
        master_share = net_amount * (master_pct / 100.0)
        company_sum = max(net_amount - master_share, 0)
        
        # Обновляем заявку в БД
        order.sum_amount = order_sum
        order.sd_price = sd_price
        try:
            setattr(order, 'zpch_sum', float(zpch_sum))
        except Exception:
            pass
        # Переводим в статус "готово к закрытию" - не completed!
        order.status = "done_pending_sum"
        # Сохраняем file_id чека, если есть
        receipt_file_id = state["data"].get("receipt_file_id")
        if receipt_file_id:
            order.receipt_file_id = receipt_file_id
        session.commit()
        
        # НЕ создаем запись в статистике здесь - только при закрытии заявки
        
        # Показываем результат
        result_text = f"📊 <b>Итоговый расчет:</b>\n\n"
        result_text += f"💰 Сумма заказа: {order_sum:.2f} руб.\n"
        result_text += f"📄 Цена СД: {sd_price:.2f} руб.\n"
        result_text += f"🔧 ЗПЧ: {zpch_sum:.2f} руб.\n"
        result_text += f"🧮 Доля мастера ({master_pct}% от {net_amount:.2f}): {master_share:.2f} руб.\n"
        result_text += f"💼 Сумма к сдаче в компанию: {company_sum:.2f} руб.\n\n"
        result_text += f"📋 Заявка #{order.order_number} готова к закрытию!\n"
        result_text += f"<i>Нажмите 'Закрыть заявку' для завершения и сдачи в кассу</i>"
        
        kb = close_order_keyboard(order_id)
        self.bot.send_message(message.chat.id, result_text, reply_markup=kb, parse_mode="HTML")
        
        # Очищаем состояние
        self.states.clear_sum_input_state(user_id)
    
    def handle_zpch_zero_callback(self, callback: types.CallbackQuery) -> None:
        """Обработать установку ЗПЧ в ноль"""
        session = get_session()
        try:
            user_id = callback.from_user.id
            state = self.states.get_sum_input_state(user_id)
            if not state:
                return
            
            state["data"]["zpch_sum"] = 0
            state["step"] = "sd_price"
            
            kb = sd_price_keyboard()
            self.bot.send_message(
                callback.message.chat.id,
                "✅ ЗПЧ установлено в 0 руб.\n\n📄 Введите цену сервисного документа (СД):",
                reply_markup=kb
            )
        finally:
            session.close()
    
    def handle_sd_zero_callback(self, callback: types.CallbackQuery) -> None:
        """Обработать установку цены СД в ноль"""
        session = get_session()
        try:
            user_id = callback.from_user.id
            state = self.states.get_sum_input_state(user_id)
            if not state:
                self.bot.answer_callback_query(callback.id, "Процесс не активен")
                return
            
            state["data"]["sd_price"] = 0
            
            if state["data"].get("zpch_sum", 0) > 0:
                state["step"] = "receipt"
                kb = receipt_keyboard()
                self.bot.send_message(
                    callback.message.chat.id,
                    "✅ Цена СД установлена в 0 руб.\n\n📎 Прикрепите чек на ЗПЧ:",
                    reply_markup=kb
                )
            else:
                # Если ЗПЧ = 0, переходим к расчету
                self._calculate_and_show_result(callback.message, user_id, session)
            self.bot.answer_callback_query(callback.id, "СД = 0")
        finally:
            session.close()
    
    def handle_attach_receipt_callback(self, callback: types.CallbackQuery) -> None:
        """Обработать прикрепление чека"""
        session = get_session()
        try:
            user_id = callback.from_user.id
            state = self.states.get_sum_input_state(user_id)
            if not state:
                self.bot.answer_callback_query(callback.id, "Процесс не активен")
                return
            
            state["step"] = "waiting_receipt"
            
            self.bot.edit_message_text(
                "📎 Ожидание чека...", 
                chat_id=callback.message.chat.id, 
                message_id=callback.message.message_id
            )
            self.bot.send_message(callback.message.chat.id, "📎 Отправьте фото чека:")
            self.bot.answer_callback_query(callback.id, "Ожидание чека")
        finally:
            session.close()
    
    def handle_skip_receipt_callback(self, callback: types.CallbackQuery) -> None:
        """Обработать пропуск чека"""
        session = get_session()
        try:
            user_id = callback.from_user.id
            state = self.states.get_sum_input_state(user_id)
            if not state:
                self.bot.answer_callback_query(callback.id, "Процесс не активен")
                return
            
            # Используем исходное сообщение
            self._calculate_and_show_result(callback.message, user_id, session)
            
            self.bot.edit_message_text(
                "⏭ Чек пропущен", 
                chat_id=callback.message.chat.id, 
                message_id=callback.message.message_id
            )
            self.bot.answer_callback_query(callback.id, "Чек пропущен")
        finally:
            session.close()
    
    def handle_cancel_sum_input_callback(self, callback: types.CallbackQuery) -> None:
        """Обработать отмену ввода суммы"""
        session = get_session()
        try:
            user_id = callback.from_user.id
            self.states.clear_sum_input_state(user_id)
            
            role = get_role(session, user_id)
            self.bot.edit_message_text(
                "❌ Ввод суммы отменен", 
                chat_id=callback.message.chat.id, 
                message_id=callback.message.message_id
            )
            kb = main_keyboard(role)
            self.bot.send_message(callback.message.chat.id, "🏠 Главное меню:", reply_markup=kb)
            self.bot.answer_callback_query(callback.id, "Ввод отменен")
        finally:
            session.close()
    
    def handle_close_order_callback(self, callback: types.CallbackQuery) -> None:
        """Обработать закрытие заявки"""
        session = get_session()
        try:
            user_id = callback.from_user.id
            order_id = int(callback.data.split(":")[1])
            
            # Проверяем, что заявка принадлежит мастеру
            order = session.query(Order).filter_by(id=order_id, assigned_to=user_id).first()
            if not order:
                self.bot.answer_callback_query(callback.id, "Нет доступа к заявке")
                return
            
            # Переводим заявку в статус completed
            order.status = "completed"
            # Автосрок гарантии по сумме закрытия (для не-гарантийных и не-отменённых)
            if not getattr(order, "is_warranty", False) and order.status != "cancelled":
                from services.warranty_service import compute_warranty
                from datetime import datetime, timezone
                closed_amount = float(order.sum_amount or order.paid_amount or 0)
                winfo = compute_warranty(closed_amount, datetime.now(timezone.utc))
                order.warranty_days = int(winfo.days)
                order.warranty_until = winfo.until
            session.commit()
            
            # Создаем запись в статистике при закрытии заявки (гарантийные не учитываем)
            if not getattr(order, "is_warranty", False):
                stat = Stat(
                    order_id=order_id,
                    equip_type=order.equip_type,
                    sum=order.sum_amount or 0,
                    master_tg=order.assigned_to,
                    refused=(order.sum_amount == 0)
                )
                session.add(stat)
                session.commit()
            
            # НЕ отправляем автоматически в кассу - только ручная сдача
            
            role = get_role(session, user_id)
            self.bot.edit_message_text(
                "✅ Заявка закрыта!", 
                chat_id=callback.message.chat.id, 
                message_id=callback.message.message_id
            )
            kb = main_keyboard(role)
            self.bot.send_message(callback.message.chat.id, "🏠 Главное меню:", reply_markup=kb)
            self.bot.answer_callback_query(callback.id, "Заявка закрыта")
        finally:
            session.close()
    
    def _send_cash_notification(self, order: Order, session) -> None:
        """Отправить уведомление в кассу о закрытии заявки"""
        try:
            from services.equipment_service import get_pct
            master_pct, company_pct = get_pct(order.equip_type)
            
            order_sum = order.sum_amount or 0
            # Предполагаем, что ЗПЧ = 0 если не указано иначе
            zpch_sum = 0  # Можно добавить поле ЗПЧ в модель если нужно
            master_share = order_sum * (master_pct / 100.0)
            company_sum = max(order_sum - zpch_sum - master_share, 0)
            
            city_id = getattr(order, 'city_id', None)
            admins_q = session.query(User).filter(User.role.in_(["owner", "director"]))
            if city_id is not None:
                admins_q = admins_q.filter((User.role == "owner") | ((User.role == "director") & (User.city_id == city_id)))
            admins = admins_q.all()
            
            cash_msg = (
                f"💼 <b>Сдана касса по заявке #{order.order_number}</b>\n"
                f"Город: {order.city_rel.name if order.city_rel else '-'}\n"
                f"Сумма заказа: {order_sum:.2f}\n"
                f"ЗПЧ: {zpch_sum:.2f}\n"
                f"Доля мастера: {master_share:.2f}\n"
                f"К сдаче: {company_sum:.2f}"
            )
            
            for admin in admins:
                try:
                    self.bot.send_message(admin.tg_id, cash_msg, parse_mode="HTML")
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Failed to send cash notification for order {order.id}: {e}")
    
    def handle_receipt_photo(self, message: types.Message) -> None:
        """Обработать фото чека"""
        session = get_session()
        try:
            user_id = message.from_user.id
            state = self.states.get_sum_input_state(user_id)
            if not state or state["step"] != "waiting_receipt":
                return
            
            # Сохраняем file_id чека
            receipt_file_id = message.photo[-1].file_id  # Берем фото наилучшего качества
            state["data"]["receipt_file_id"] = receipt_file_id
            
            # Используем исходное сообщение
            self._calculate_and_show_result(message, user_id, session)
            
            self.bot.send_message(message.chat.id, "✅ Чек получен!")
        finally:
            session.close()

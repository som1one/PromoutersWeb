"""
Сервис для планирования заявок на будущие даты.
Содержит логику уведомления мастеров о запланированных заявках.
"""

import logging
from datetime import datetime, timedelta
from typing import List
from db import get_session
from model import Order, User
from handlers.order_handlers import OrderHandler

logger = logging.getLogger(__name__)


class SchedulerService:
    """Сервис для планирования заявок"""
    
    def __init__(self, bot):
        self.bot = bot
        self.order_handler = OrderHandler(bot)
    
    def schedule_order_for_date(self, order: Order, target_date: datetime) -> None:
        """Запланировать заявку на определенную дату"""
        session = get_session()
        try:
            order.order_date = target_date
            order.status = "scheduled"
            session.commit()
            
            # Уведомляем мастера о запланированной заявке
            if order.assigned_to:
                self._notify_master_scheduled(order, session)
                
        except Exception as e:
            logger.error(f"Failed to schedule order {order.id}: {e}")
        finally:
            session.close()
    
    def _notify_master_scheduled(self, order: Order, session) -> None:
        """Уведомить мастера о запланированной заявке"""
        try:
            master = session.query(User).filter_by(tg_id=order.assigned_to).first()
            if master:
                order_date_str = order.order_date.strftime("%d.%m.%Y")
                message_text = f"📅 <b>Заявка #{order.order_number} запланирована на {order_date_str}</b>\n\n"
                message_text += f"🏙 Город: {order.city_rel.name if order.city_rel else 'Не указан'}\n"
                message_text += f"⏰ Время: {order.time_from} - {order.time_to}\n"
                message_text += f"🔧 Тип техники: {self._get_equip_type_name(order.equip_type)}\n\n"
                message_text += f"<i>Заявка будет активна утром {order_date_str}</i>"
                
                self.bot.send_message(order.assigned_to, message_text, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Failed to notify master about scheduled order {order.assigned_to}: {e}")
    
    def process_scheduled_orders(self) -> None:
        """Обработать запланированные заявки на сегодня"""
        session = get_session()
        try:
            today = datetime.now().date()
            
            # Находим заявки, запланированные на сегодня
            scheduled_orders = session.query(Order).filter(
                Order.status == "scheduled",
                Order.order_date.isnot(None)
            ).all()
            
            for order in scheduled_orders:
                if order.order_date.date() == today:
                    # Активируем заявку
                    order.status = "assigned"
                    session.commit()
                    
                    # Уведомляем мастера
                    self._notify_master_activated(order, session)
                    
        except Exception as e:
            logger.error(f"Failed to process scheduled orders: {e}")
        finally:
            session.close()
    
    def _notify_master_activated(self, order: Order, session) -> None:
        """Уведомить мастера об активации запланированной заявки"""
        try:
            master = session.query(User).filter_by(tg_id=order.assigned_to).first()
            if master:
                from handlers.menu_kb import master_new_order_kb
                kb = master_new_order_kb(order.id)
                
                message_text = f"🎯 <b>Заявка #{order.order_number} активирована!</b>\n\n"
                message_text += f"🏙 Город: {order.city_rel.name if order.city_rel else 'Не указан'}\n"
                message_text += f"⏰ Время: {order.time_from} - {order.time_to}\n"
                message_text += f"🔧 Тип техники: {self._get_equip_type_name(order.equip_type)}\n\n"
                message_text += f"<i>Нажмите 'Принять' для просмотра полной информации о заявке</i>"
                
                self.bot.send_message(order.assigned_to, message_text, reply_markup=kb, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Failed to notify master about activated order {order.assigned_to}: {e}")
    
    def _get_equip_type_name(self, code):
        """Получить название типа техники по коду"""
        from handlers.utils import get_equip_type_name
        return get_equip_type_name(code)
    
    def get_scheduled_orders_for_master(self, master_tg_id: int) -> List[Order]:
        """Получить запланированные заявки для мастера"""
        session = get_session()
        try:
            return session.query(Order).filter(
                Order.assigned_to == master_tg_id,
                Order.status == "scheduled"
            ).order_by(Order.order_date).all()
        finally:
            session.close()

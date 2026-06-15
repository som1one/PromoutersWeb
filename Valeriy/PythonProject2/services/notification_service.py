"""
Сервис для отправки уведомлений через VK API.
Используется как из бота, так и из веб-интерфейса.
"""

import os
import logging
from typing import Optional
from dotenv import load_dotenv
import vk_api
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id
from vk_api.exceptions import ApiError

from db import get_session
from model import User, Order
from handlers.utils import get_equip_type_name

logger = logging.getLogger(__name__)

# Загружаем переменные окружения
try:
    if os.path.exists('local.env'):
        load_dotenv('local.env')
    else:
        load_dotenv()
except Exception:
    pass


class NotificationService:
    """Сервис для отправки уведомлений через VK API"""
    
    def __init__(self):
        """Инициализация сервиса"""
        self.token = os.getenv("VK_BOT_TOKEN")
        if not self.token:
            logger.warning("VK_BOT_TOKEN не найден, уведомления не будут отправляться")
            self.vk = None
        else:
            try:
                vk_session = vk_api.VkApi(token=self.token)
                self.vk = vk_session.get_api()
                logger.info("✅ NotificationService инициализирован")
            except Exception as e:
                logger.error(f"Ошибка инициализации VK API: {e}")
                self.vk = None
    
    def send_message(self, user_id: int, message: str, keyboard: Optional[VkKeyboard] = None) -> bool:
        """Отправить сообщение пользователю через VK API"""
        if not self.vk:
            logger.warning(f"VK API не инициализирован, сообщение не отправлено пользователю {user_id}")
            return False
        
        try:
            params = {
                "user_id": user_id,
                "message": message,
                "random_id": get_random_id(),
            }
            
            if keyboard:
                params["keyboard"] = keyboard.get_keyboard()
            
            self.vk.messages.send(**params)
            logger.info(f"📤 Отправлено сообщение пользователю {user_id}")
            return True
        except ApiError as e:
            logger.warning(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при отправке сообщения пользователю {user_id}: {e}")
            return False
    
    def notify_master(self, order: Order, session) -> None:
        """Уведомить мастера о новой заявке"""
        if not order.assigned_to:
            return
        
        try:
            master = session.query(User).filter_by(tg_id=order.assigned_to).first()
            if not master:
                logger.warning(f"Мастер с tg_id={order.assigned_to} не найден")
                return
            
            # Создаем клавиатуру для мастера
            kb = VkKeyboard(inline=True)
            kb.add_button("✅ Принять", color=VkKeyboardColor.POSITIVE, 
                         payload={"cmd": "accept", "order_id": order.id})
            
            # Формируем сообщение
            city_name = order.city_rel.name if order.city_rel else "Не указан"
            equip_type_name = get_equip_type_name(order.equip_type)
            
            message_text = f"🎯 Вам назначена новая заявка №{order.order_number}\n\n"
            message_text += f"🏙 Город: {city_name}\n"
            message_text += f"⏰ Время: {order.time_from} - {order.time_to}\n"
            message_text += f"🔧 Тип техники: {equip_type_name}\n\n"
            message_text += "Нажмите 'Принять' для просмотра полной информации о заявке"
            
            self.send_message(order.assigned_to, message_text, kb)
        except Exception as e:
            logger.warning(f"Не удалось уведомить мастера {order.assigned_to} о заявке {order.id}: {e}")
    
    def notify_directors(self, order: Order, session) -> None:
        """Уведомить директоров о новой заявке"""
        try:
            # Получаем всех директоров
            directors = session.query(User).filter(User.role == "director").all()
            
            for director in directors:
                try:
                    # Уведомляем директора, если заявка привязана к его городу
                    if order.city_id and director.city_id == order.city_id:
                        self._notify_director_about_order(director, order, session)
                except Exception as e:
                    logger.warning(f"Не удалось уведомить директора {director.tg_id}: {e}")
        except Exception as e:
            logger.warning(f"Ошибка при уведомлении директоров о заявке {order.id}: {e}")
    
    def _notify_director_about_order(self, director: User, order: Order, session) -> None:
        """Уведомить конкретного директора о заявке"""
        try:
            city_name = order.city_rel.name if order.city_rel else "Не указан"
            equip_type_name = get_equip_type_name(order.equip_type)
            
            if order.assigned_to:
                master = session.query(User).filter_by(tg_id=order.assigned_to).first()
                master_name = master.full_name or master.name if master else f"ID {order.assigned_to}"
                message_text = f"📋 Заявка #{order.order_number} назначена мастеру\n\n"
                message_text += f"🔧 Мастер: {master_name}\n"
            else:
                message_text = f"📋 Новая заявка #{order.order_number}\n\n"
            
            message_text += f"🏙 Город: {city_name}\n"
            message_text += f"📍 Адрес: {order.street}, д. {order.house}, кв. {order.flat}\n"
            message_text += f"🔧 Техника: {equip_type_name}\n"
            message_text += f"📝 Описание: {order.short_desc}\n"
            
            if not order.assigned_to:
                # Если заявка не назначена, предлагаем взять её или назначить мастера
                kb = VkKeyboard(inline=True)
                kb.add_button("✅ Взять себе", color=VkKeyboardColor.POSITIVE,
                             payload={"cmd": "take_order", "order_id": order.id})
                kb.add_line()
                kb.add_button("👤 Назначить", color=VkKeyboardColor.PRIMARY,
                             payload={"cmd": "assign_menu", "order_id": order.id})
                self.send_message(director.tg_id, message_text, kb)
            else:
                self.send_message(director.tg_id, message_text)
        except Exception as e:
            logger.warning(f"Не удалось уведомить директора {director.tg_id}: {e}")
    
    def notify_owners(self, order: Order, session) -> None:
        """Уведомить собственников о новой заявке"""
        try:
            owners = session.query(User).filter(User.role == "owner").all()
            
            for owner in owners:
                try:
                    master = session.query(User).filter_by(tg_id=order.assigned_to).first() if order.assigned_to else None
                    master_name = master.full_name or master.name if master else f"ID {order.assigned_to}" if order.assigned_to else "Не назначен"
                    
                    city_name = order.city_rel.name if order.city_rel else "Не указан"
                    equip_type_name = get_equip_type_name(order.equip_type)
                    
                    message_text = f"📋 Заявка #{order.order_number} назначена мастеру\n\n"
                    message_text += f"🔧 Мастер: {master_name}\n"
                    message_text += f"🏙 Город: {city_name}\n"
                    message_text += f"📍 Адрес: {order.street}, д. {order.house}, кв. {order.flat}\n"
                    message_text += f"🔧 Техника: {equip_type_name}\n"
                    message_text += f"📝 Описание: {order.short_desc}\n"
                    
                    self.send_message(owner.tg_id, message_text)
                except Exception as e:
                    logger.warning(f"Не удалось уведомить собственника {owner.tg_id}: {e}")
        except Exception as e:
            logger.warning(f"Ошибка при уведомлении собственников о заявке {order.id}: {e}")


# Глобальный экземпляр сервиса
_notification_service = None


def get_notification_service() -> NotificationService:
    """Получить глобальный экземпляр сервиса уведомлений"""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service


def notify_order_created(order: Order, session) -> None:
    """
    Уведомить всех заинтересованных пользователей о создании заявки.
    Используется из веб-интерфейса и бота.
    """
    service = get_notification_service()
    
    # Уведомляем мастера, если заявка назначена
    if order.assigned_to:
        service.notify_master(order, session)
    
    # Уведомляем директоров
    service.notify_directors(order, session)
    
    # Уведомляем собственников
    service.notify_owners(order, session)


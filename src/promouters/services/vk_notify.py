"""Send VK notifications to masters when orders are created/assigned.

Uses VK_BOT_TOKEN from environment if available. Silently no-ops if
the token is not configured (web-only deployments without VK bot).
"""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from promouters.models.service_ops import Order
    from promouters.models.users import User

logger = logging.getLogger(__name__)

_vk_api = None
_initialized = False


def _get_vk():
    """Lazy-init VK API connection."""
    global _vk_api, _initialized
    if _initialized:
        return _vk_api
    _initialized = True

    token = os.getenv("VK_BOT_TOKEN")
    if not token:
        logger.info("VK_BOT_TOKEN not set — VK notifications disabled")
        return None

    try:
        import vk_api
        from vk_api.utils import get_random_id  # noqa: F401

        session = vk_api.VkApi(token=token)
        _vk_api = session.get_api()
        logger.info("VK notification service initialized")
    except Exception as e:
        logger.warning(f"Failed to init VK API for notifications: {e}")
        _vk_api = None

    return _vk_api


def _send(user_id: int, message: str) -> bool:
    """Send a VK message. Returns True on success."""
    vk = _get_vk()
    if not vk:
        return False
    try:
        from vk_api.utils import get_random_id

        vk.messages.send(
            user_id=user_id,
            message=message,
            random_id=get_random_id(),
        )
        return True
    except Exception as e:
        logger.warning(f"Failed to send VK message to {user_id}: {e}")
        return False


def notify_master_new_order(order: "Order", master: "User | None" = None) -> None:
    """Notify a master via VK about a new/assigned order."""
    if not order.assigned_to:
        return

    master_name = ""
    if master:
        master_name = master.full_name or master.name or ""

    address_parts = [p for p in (order.street, order.house, order.flat) if p]
    address = ", ".join(address_parts) if address_parts else "не указан"

    time_str = ""
    if order.time_from:
        time_str = f"{order.time_from}"
        if order.time_to:
            time_str += f" – {order.time_to}"

    msg = (
        f"🆕 Новая заявка #{order.order_number}\n\n"
        f"📍 Адрес: {address}\n"
    )
    if time_str:
        msg += f"⏰ Время: {time_str}\n"
    if order.equip_type:
        msg += f"🔧 Техника: {order.equip_type}\n"
    if order.client_phone:
        msg += f"📞 Клиент: {order.client_phone}\n"
    if order.short_desc:
        msg += f"📝 {order.short_desc}\n"

    msg += "\nОткройте бот для просмотра деталей."

    _send(order.assigned_to, msg)

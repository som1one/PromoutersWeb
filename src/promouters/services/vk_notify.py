"""Send VK notifications to masters when orders are created/assigned.

Reads the VK community token from ``Settings.vk_bot_token`` (env ``VK_BOT_TOKEN``).
It must be the same community token the bot (Valeriy/PythonProject2) uses.
Silently no-ops — but logs a clear warning — if the token or the ``vk_api``
package is not available (web-only deployments without VK bot).
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


def _get_token() -> str | None:
    """Prefer the app Settings (loads .env), fall back to the raw env var."""
    try:
        from promouters.core.config import get_settings

        token = get_settings().vk_bot_token
        if token:
            return token
    except Exception:  # noqa: BLE001 — settings must never break notifications
        pass
    return os.getenv("VK_BOT_TOKEN")


def _get_vk():
    """Lazy-init VK API connection."""
    global _vk_api, _initialized
    if _initialized:
        return _vk_api
    _initialized = True

    token = _get_token()
    if not token:
        logger.warning(
            "VK_BOT_TOKEN не задан — ВК-уведомления мастерам отключены. "
            "Добавьте VK_BOT_TOKEN в окружение веб-приложения."
        )
        return None

    try:
        import vk_api

        session = vk_api.VkApi(token=token)
        _vk_api = session.get_api()
        logger.info("VK notification service initialized")
    except Exception as e:  # noqa: BLE001
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
        logger.info(f"VK notification sent to master {user_id}")
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to send VK message to {user_id}: {e}")
        return False


def _equip_type_name(order: "Order") -> str | None:
    if not order.equip_type:
        return None
    try:
        from promouters.utils.order_helpers import get_equip_type_name

        return get_equip_type_name(order.equip_type) or order.equip_type
    except Exception:  # noqa: BLE001
        return order.equip_type


def notify_master_new_order(order: "Order", master: "User | None" = None) -> bool:
    """Notify a master via VK about a new/assigned order.

    Returns True only if the VK message was actually sent.
    """
    if not order.assigned_to:
        return False

    address_parts = [p for p in (order.street, order.house, order.flat) if p]
    address = ", ".join(address_parts) if address_parts else None

    city = None
    try:
        city = order.city_rel.name if order.city_rel else None
    except Exception:  # noqa: BLE001 — city may not be loaded / detached
        city = None

    time_str = ""
    if order.time_from:
        time_str = f"{order.time_from}"
        if order.time_to:
            time_str += f" – {order.time_to}"

    msg = f"🎯 Вам назначена новая заявка №{order.order_number}\n\n"
    if city:
        msg += f"🏙 Город: {city}\n"
    if address:
        msg += f"📍 Адрес: {address}\n"
    if time_str:
        msg += f"⏰ Время: {time_str}\n"
    equip = _equip_type_name(order)
    if equip:
        msg += f"🔧 Техника: {equip}\n"
    if order.client_phone:
        msg += f"📞 Клиент: {order.client_phone}\n"
    if order.short_desc:
        msg += f"📝 {order.short_desc}\n"

    msg += "\nОткройте бот, чтобы принять заявку."

    return _send(order.assigned_to, msg)

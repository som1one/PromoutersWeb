"""Photo report reminder for promoters after session completion.

Sends «Скинь фотоотчёт куратору» via VK API after a session transitions
to completed status. Runs in a background thread to avoid blocking the
bot's response. Retries up to 2 additional attempts with 30-second intervals
on failure.

Requirements: 8.1, 8.2, 8.3, 8.4
"""
from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)

PHOTO_REMINDER_MESSAGE = "Скинь фотоотчёт куратору"
MAX_RETRIES = 2
RETRY_INTERVAL_SECONDS = 30


def send_photo_report_reminder(vk_user_id: str | int | None) -> None:
    """Send a photo report reminder to the promoter in a background thread.

    This function is non-blocking: it spawns a daemon thread that handles
    the message delivery with retries.

    Args:
        vk_user_id: The VK user ID of the promoter. If None or empty,
                    the reminder is skipped and the event is logged.
    """
    if not vk_user_id:
        logger.info(
            "Photo report reminder skipped: promoter has no linked VK user ID"
        )
        return

    # Convert to int for the VK API call
    try:
        user_id_int = int(vk_user_id)
    except (ValueError, TypeError):
        logger.warning(
            f"Photo report reminder skipped: invalid VK user ID '{vk_user_id}'"
        )
        return

    thread = threading.Thread(
        target=_send_reminder_with_retries,
        args=(user_id_int,),
        daemon=True,
        name=f"photo-reminder-{user_id_int}",
    )
    thread.start()


def _get_random_id() -> int:
    """Get a random ID for VK message deduplication.

    Falls back to Python's random module if vk_api is not available.
    """
    try:
        from vk_api.utils import get_random_id
        return get_random_id()
    except ImportError:
        import random
        return random.getrandbits(64)


def _send_reminder_with_retries(user_id: int) -> bool:
    """Send the photo reminder message with retry logic.

    Attempts to send the message once, then retries up to MAX_RETRIES
    additional times with RETRY_INTERVAL_SECONDS between attempts.

    Args:
        user_id: Integer VK user ID.

    Returns:
        True if the message was sent successfully, False otherwise.
    """
    from promouters.services.vk_notify import _get_vk

    for attempt in range(1, MAX_RETRIES + 2):  # 1 initial + 2 retries = 3 total
        vk = _get_vk()
        if not vk:
            logger.warning(
                f"Photo report reminder attempt {attempt}/{MAX_RETRIES + 1} failed: "
                f"VK API not available (user_id={user_id})"
            )
            if attempt <= MAX_RETRIES:
                time.sleep(RETRY_INTERVAL_SECONDS)
            continue

        try:
            vk.messages.send(
                user_id=user_id,
                message=PHOTO_REMINDER_MESSAGE,
                random_id=_get_random_id(),
            )
            logger.info(
                f"Photo report reminder sent successfully to user_id={user_id} "
                f"(attempt {attempt}/{MAX_RETRIES + 1})"
            )
            return True
        except Exception as e:
            logger.warning(
                f"Photo report reminder attempt {attempt}/{MAX_RETRIES + 1} failed "
                f"for user_id={user_id}: {e}"
            )
            if attempt <= MAX_RETRIES:
                time.sleep(RETRY_INTERVAL_SECONDS)

    logger.error(
        f"Photo report reminder delivery failed after {MAX_RETRIES + 1} attempts "
        f"for user_id={user_id}"
    )
    return False

"""Configuration helpers for VK bot."""

import os
from datetime import timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TZ_NAME = os.getenv("DEFAULT_TZ_NAME", "Europe/Moscow")

try:
    DEFAULT_TZ = ZoneInfo(DEFAULT_TZ_NAME)
except ZoneInfoNotFoundError:
    DEFAULT_TZ = timezone.utc



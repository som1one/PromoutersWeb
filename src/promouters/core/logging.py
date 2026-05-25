import json
import logging
import logging.config
from pathlib import Path
from typing import Any

import yaml

from promouters.core.config import Settings


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


def configure_logging(settings: Settings) -> None:
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)

    config_path = Path(settings.log_config_path)
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as file:
            config = yaml.safe_load(file)
    else:
        config = {
            "version": 1,
            "disable_existing_loggers": False,
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": settings.log_level,
                }
            },
            "root": {"level": settings.log_level, "handlers": ["console"]},
        }

    config["root"]["level"] = settings.log_level

    for handler in config.get("handlers", {}).values():
        handler["level"] = settings.log_level
        if settings.log_json and handler.get("class") == "logging.StreamHandler":
            handler["formatter"] = "json"

    if settings.log_json:
        config.setdefault("formatters", {})
        config["formatters"]["json"] = {"()": JsonFormatter}

    logging.config.dictConfig(config)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


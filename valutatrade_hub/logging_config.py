"""Настройка логирования: текстовый или JSON-формат, ротация по размеру."""
from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .infra.settings import SettingsLoader

_LOGGER_NAME = "valutatrade"

# Поля, которые декоратор @log_action добавляет в LogRecord.
_STRUCTURED_FIELDS = (
    "action", "username", "user_id", "currency", "amount",
    "rate", "base", "result", "error_type", "error_message", "context",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
        }
        has_structured = False
        for key in _STRUCTURED_FIELDS:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
                has_structured = True
        if not has_structured:
            payload["message"] = record.getMessage()
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str | None = None) -> logging.Logger:
    settings = SettingsLoader()
    log_dir = Path(settings.get("log_dir"))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / settings.get("log_file")

    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(level or settings.get("log_level", "INFO"))

    if logger.handlers:  # идемпотентно
        return logger

    handler = RotatingFileHandler(
        log_file,
        maxBytes=int(settings.get("log_max_bytes")),
        backupCount=int(settings.get("log_backup_count")),
        encoding="utf-8",
    )

    if settings.get("log_format") == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(levelname)s %(asctime)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        ))

    logger.addHandler(handler)
    logger.propagate = False
    return logger
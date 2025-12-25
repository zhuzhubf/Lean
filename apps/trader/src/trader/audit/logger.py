"""JSON logger helper."""

from __future__ import annotations

import json
import logging
from typing import Any, Mapping


class JsonFormatter(logging.Formatter):
    """Simple JSON formatter for structured logs."""

    def format(self, record: logging.LogRecord) -> str:  # pragma: no cover - thin wrapper
        payload = {
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.args and isinstance(record.args, Mapping):
            payload.update(record.args)
        if record.__dict__.get("extra"):
            payload.update(record.__dict__["extra"])
        return json.dumps(payload)


def configure_json_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def json_dumps(data: Mapping[str, Any]) -> str:
    return json.dumps(data, default=str)


__all__ = ["configure_json_logging", "json_dumps", "JsonFormatter"]

"""Structured JSON logging for production environments."""

from __future__ import annotations

import contextvars
import json
import logging
import traceback
from datetime import datetime, timezone

# ContextVar holding the current request ID for log correlation.
request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)


class JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON for structured log ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        rid = request_id_ctx.get()
        if rid is not None:
            log_entry["request_id"] = rid
        if record.exc_info and record.exc_info[1] is not None:
            log_entry["exception"] = traceback.format_exception(*record.exc_info)
        return json.dumps(log_entry, default=str)


def configure_structured_logging() -> None:
    """Replace root logger handlers with a JSON-formatted stderr handler."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)

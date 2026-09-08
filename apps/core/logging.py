"""Logging helpers: request-ID injection and a minimal JSON formatter.

Deliberately hand-rolled rather than pulling in a logging library — this is
a handful of lines with no dependency justification (see docs/development/
coding-standards.md's "justified dependency" rule).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from apps.core.middleware import get_current_request_id


class RequestIDLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_current_request_id()
        return True


class JSONLogFormatter(logging.Formatter):
    """Structured log line for production. Never include raw exception args
    that might carry sensitive values (passwords, tokens, employee data) —
    only the rendered, already-sanitized message.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)

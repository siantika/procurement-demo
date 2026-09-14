"""Small structured JSON formatter without external dependencies."""

import json
import logging
from datetime import UTC, datetime

from django.conf import settings


class JsonLogFormatter(logging.Formatter):
    included_fields = (
        "correlation_id",
        "operation",
        "from_status",
        "to_status",
        "method",
        "route",
        "status_code",
        "duration_ms",
        "outcome",
        "safe_error_code",
        "entity_type",
        "entity_id",
        "actor_id",
        "diagnostic_reference",
    )

    def format(self, record):
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "process": record.processName,
            "environment": getattr(settings, "APP_ENV", "unknown"),
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in self.included_fields:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__
        return json.dumps(
            payload, ensure_ascii=False, separators=(",", ":")
        )

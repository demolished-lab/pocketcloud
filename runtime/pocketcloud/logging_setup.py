from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    _allowed_extra_fields = {"component", "job_id", "handler_id", "diagnostic_code"}

    def format(self, record: logging.LogRecord) -> str:
        component = getattr(record, "component", record.name)
        item: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "severity": record.levelname.lower(),
            "component": str(component)[:80],
            "message": record.getMessage()[:300],
        }
        for field in self._allowed_extra_fields - {"component"}:
            value = getattr(record, field, None)
            if value is not None:
                item[field] = str(value)[:128]
        return json.dumps(item, ensure_ascii=False, separators=(",", ":"))


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("uvicorn.error").propagate = True

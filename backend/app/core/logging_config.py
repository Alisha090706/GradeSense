"""
Structured logging — Phase 14.

JSON-line logs (one JSON object per line) rather than default Python
logging's free-text format, so logs are actually queryable once this runs
anywhere with real log aggregation (grep/jq locally, or any log platform
in a real deployment) — free-text logs mean writing regexes forever;
structured logs mean filtering on real fields from day one.

Deliberately NOT capturing request/response bodies — submission content,
auth tokens, and email/password fields could all end up in a body, and
logging those is a real data-handling decision this project shouldn't
make silently. What IS logged (method, path, status, duration, a request
ID) is enough to debug "why is this endpoint slow" or "what's erroring"
without becoming a second copy of sensitive data sitting in log files.
"""
import json
import logging
import sys
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
        }
        # Anything passed via logger.info("msg", extra={...}) rides along —
        # this is how request_logging_middleware attaches structured fields
        # (method/path/status/duration/request_id) without stuffing them into
        # the message string itself.
        for key, value in getattr(record, "extra_fields", {}).items():
            payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


request_logger = logging.getLogger("gradesense.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 1)

        request_logger.info(
            f"{request.method} {request.url.path} -> {response.status_code}",
            extra={"extra_fields": {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            }},
        )
        response.headers["X-Request-ID"] = request_id
        return response

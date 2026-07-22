"""
core/logging_config.py's JsonFormatter — mirrors the real verification
run while building Phase 14: log records produce valid, correctly-keyed
JSON with extra_fields flattened into the top-level object, and
exceptions are captured too.
"""
import json
import logging

from app.core.logging_config import JsonFormatter


def _capture(logger_name="test.logging_config"):
    import io
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger(logger_name)
    logger.handlers = [handler]
    logger.setLevel("INFO")
    logger.propagate = False
    return logger, stream


class TestJsonFormatter:
    def test_produces_valid_json_with_extra_fields(self):
        logger, stream = _capture()
        logger.info(
            "GET /api/v1/courses -> 200",
            extra={"extra_fields": {"request_id": "abc-123", "status": 200, "duration_ms": 12.3}},
        )
        parsed = json.loads(stream.getvalue().strip())
        assert parsed["level"] == "INFO"
        assert parsed["message"] == "GET /api/v1/courses -> 200"
        assert parsed["request_id"] == "abc-123"
        assert parsed["status"] == 200
        assert parsed["duration_ms"] == 12.3

    def test_captures_exceptions(self):
        logger, stream = _capture("test.logging_config.exc")
        try:
            raise ValueError("boom")
        except ValueError:
            logger.exception("something broke")
        parsed = json.loads(stream.getvalue().strip())
        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]

    def test_no_extra_fields_still_produces_valid_json(self):
        logger, stream = _capture("test.logging_config.plain")
        logger.info("plain message, no extras")
        parsed = json.loads(stream.getvalue().strip())
        assert parsed["message"] == "plain message, no extras"

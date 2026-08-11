"""Application logging with basic secret redaction."""

import logging
import os
import re

_API_KEY_PATTERN = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{8,}|AIza[A-Za-z0-9_-]{30,})\b")


class RedactingFormatter(logging.Formatter):
    """Remove API-key-shaped values from rendered log messages."""

    def format(self, record: logging.LogRecord) -> str:
        rendered = super().format(record)
        return _API_KEY_PATTERN.sub("[REDACTED_API_KEY]", rendered)


def configure_logging(level: str | None = None) -> None:
    """Configure a concise root logger for local development and tests."""
    resolved_level = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    handler = logging.StreamHandler()
    handler.setFormatter(
        RedactingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(resolved_level)

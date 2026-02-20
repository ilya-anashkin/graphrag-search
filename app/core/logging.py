"""Structured logging setup."""

import logging
from contextvars import ContextVar
from typing import Any

import structlog

REQUEST_ID_CONTEXT_KEY = "request_id"
DEFAULT_REQUEST_ID = "unknown"

request_id_context: ContextVar[str] = ContextVar(REQUEST_ID_CONTEXT_KEY, default=DEFAULT_REQUEST_ID)


def _add_request_id(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Inject request id from context into every log event."""

    event_dict[REQUEST_ID_CONTEXT_KEY] = request_id_context.get()
    return event_dict


def configure_logging(log_level: str) -> None:
    """Configure standard logging and structlog processors."""

    logging.basicConfig(level=log_level, format="%(message)s")
    structlog.configure(
        processors=[
            _add_request_id,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return configured structured logger."""

    return structlog.get_logger(name)

"""Structured JSON logging with correlation context and secret redaction.

Logs never contain secrets or raw evidence content (SEC-006, PRIV-004, OBS-001).
"""

import logging
import re
import sys
from contextvars import ContextVar

import structlog

# Correlation identifiers propagated across a request / investigation.
correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)
investigation_id_var: ContextVar[str | None] = ContextVar("investigation_id", default=None)

# Keys whose values must never be logged.
_SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "jwt_secret",
    "authorization",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "openai_api_key",
    "virustotal_api_key",
    "etherscan_api_key",
    "ibmz_api_token",
    "s3_secret_key",
    "secret",
}

_SECRET_PATTERN = re.compile(r"(bearer\s+)[A-Za-z0-9._\-]+", re.IGNORECASE)


def _redact_processor(_logger, _method, event_dict):
    """Redact sensitive keys and bearer tokens from log event dicts."""
    for key in list(event_dict.keys()):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "***REDACTED***"
        elif isinstance(event_dict[key], str):
            event_dict[key] = _SECRET_PATTERN.sub(r"\1***REDACTED***", event_dict[key])
    return event_dict


def _context_processor(_logger, _method, event_dict):
    """Inject correlation and investigation IDs when present."""
    cid = correlation_id_var.get()
    iid = investigation_id_var.get()
    if cid:
        event_dict.setdefault("correlation_id", cid)
    if iid:
        event_dict.setdefault("investigation_id", iid)
    return event_dict


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog to emit JSON lines to stdout."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _context_processor,
            _redact_processor,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "traceguard") -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger."""
    return structlog.get_logger(name)

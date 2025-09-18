"""Centralized logging configuration.

This module provides a standard Python logging configuration using dictConfig.
Call configure_logging() as early as possible in application entry points.
"""

import logging
import logging.config
import os
import json
from typing import Optional, Dict, Any


def _get_default_level() -> str:
    level = os.getenv("LOG_LEVEL") or os.getenv("PY_LOG_LEVEL")
    return level or "INFO"


class ExtraFormatter(logging.Formatter):
    """Formatter that appends non-standard LogRecord attributes as key=value pairs.

    Keeps logs compact and readable while surfacing useful context.
    """

    # Standard LogRecord attributes from Python's logging module
    STANDARD_ATTRS = {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "process",
        "processName",
        "asctime",
    }

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        # Collect extra fields not in the standard attributes or noisy vendor keys
        extras: Dict[str, Any] = {}
        for key, value in record.__dict__.items():
            if key in self.STANDARD_ATTRS:
                continue
            if key in {"message", "color_message"}:
                continue
            extras[key] = value

        if not extras:
            return base

        # Render extras as key=value pairs (JSON-encode complex values)
        parts = []
        for k, v in extras.items():
            if isinstance(v, (str, int, float, bool)) or v is None:
                parts.append(f"{k}={v}")
            else:
                try:
                    parts.append(f"{k}={json.dumps(v, ensure_ascii=False)}")
                except Exception:
                    parts.append(f"{k}={repr(v)}")
        return f"{base} | {' '.join(parts)}"


def configure_logging(level: Optional[str] = None) -> None:
    """Configure application logging via dictConfig without overriding root.

    - Level can be overridden via argument or LOG_LEVEL env var.
    - Uses a concise console formatter with timestamps.
    - Avoids touching uvicorn's root handlers to preserve colors.
    """
    effective_level = (level or _get_default_level()).upper()

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "app_console": {
                "()": "agent.logging_config.ExtraFormatter",
                "format": "%(asctime)s %(levelname)s %(name)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            }
        },
        "handlers": {
            "app_console": {
                "class": "logging.StreamHandler",
                "level": effective_level,
                "formatter": "app_console",
                "stream": "ext://sys.stdout",
            }
        },
        # Do NOT set root; preserve uvicorn's default colored handlers
        "loggers": {
            # Our application namespaces
            "agent": {
                "level": effective_level,
                "handlers": ["app_console"],
                "propagate": False,
            },
            "server": {
                "level": effective_level,
                "handlers": ["app_console"],
                "propagate": False,
            },
            "openwebui_pipeline": {
                "level": effective_level,
                "handlers": ["app_console"],
                "propagate": False,
            },
            # Keep common noisy libs reasonable
            "httpx": {"level": "WARNING", "propagate": True},
            "requests": {"level": "WARNING", "propagate": True},
        },
    }

    logging.config.dictConfig(config)

"""Langfuse observability — initializes tracing if keys are configured."""

import logging
from typing import Any

logger = logging.getLogger(__name__)

_langfuse = None
_enabled = False


def init_langfuse() -> None:
    """Initialize Langfuse client from settings. No-op if keys are missing."""
    global _langfuse, _enabled
    try:
        from config.settings import get_settings
        settings = get_settings()
        if not settings.langfuse_public_key or not settings.langfuse_secret_key:
            logger.info("Langfuse keys not configured — tracing disabled")
            return

        from langfuse import Langfuse
        _langfuse = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_base_url,
        )
        _enabled = True
        logger.info("Langfuse tracing enabled")
    except Exception:
        logger.warning("Failed to initialize Langfuse", exc_info=True)


def is_enabled() -> bool:
    return _enabled


def get_langfuse():
    """Return Langfuse client or None."""
    return _langfuse if _enabled else None


def flush() -> None:
    """Flush pending Langfuse events."""
    if _langfuse:
        try:
            _langfuse.flush()
        except Exception:
            logger.warning("Failed to flush Langfuse", exc_info=True)


def shutdown() -> None:
    """Shutdown Langfuse client."""
    if _langfuse:
        try:
            _langfuse.shutdown()
        except Exception:
            logger.warning("Failed to shutdown Langfuse", exc_info=True)

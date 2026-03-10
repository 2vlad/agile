"""Langfuse observability — initializes tracing if keys are configured."""

import logging
from contextlib import contextmanager
from typing import Any, Generator

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


def create_trace(
    name: str,
    user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
) -> Any:
    """Create a new Langfuse trace. Returns trace object or None."""
    if not _enabled or not _langfuse:
        return None
    try:
        return _langfuse.trace(
            name=name,
            user_id=user_id,
            metadata=metadata or {},
            tags=tags or [],
        )
    except Exception:
        logger.warning("Failed to create Langfuse trace", exc_info=True)
        return None


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

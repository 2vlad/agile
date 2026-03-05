"""Gold standard: Async singleton with lazy initialization.

Module-level private variable (_resource) starts as None.
get_resource() uses asyncio.Lock for thread-safe lazy init.
Always provide a close/cleanup function that resets to None.
"""
import asyncio
import logging

logger = logging.getLogger(__name__)

_client: SomeAsyncClient | None = None
_lock: asyncio.Lock | None = None


async def get_client() -> SomeAsyncClient:
    global _client, _lock
    if _lock is None:
        _lock = asyncio.Lock()
    if _client is None:
        async with _lock:
            if _client is None:  # double-check after acquiring lock
                _client = await _create_client()
    return _client


async def close_client() -> None:
    global _client
    if _client:
        await _client.close()
        _client = None

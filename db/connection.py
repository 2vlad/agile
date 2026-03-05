import asyncpg
import ssl
import logging
from urllib.parse import urlparse

from config.settings import get_settings

logger = logging.getLogger(__name__)
_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await _create_pool()
    return _pool


async def _create_pool() -> asyncpg.Pool:
    settings = get_settings()
    parsed = urlparse(settings.database_url)
    use_ssl = parsed.port == 6432 or "sslmode=require" in settings.database_url
    ssl_ctx = ssl.create_default_context() if use_ssl else None
    return await asyncpg.create_pool(
        settings.database_url,
        ssl=ssl_ctx,
        statement_cache_size=settings.db_statement_cache_size,
        min_size=2,
        max_size=10,
    )


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def init_db() -> None:
    from pathlib import Path

    pool = await get_pool()
    schema_path = Path(__file__).parent / "schema.sql"
    schema = schema_path.read_text()
    async with pool.acquire() as conn:
        await conn.execute(schema)
    logger.info("Database initialized")

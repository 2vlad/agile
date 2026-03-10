import asyncio
import ssl
import logging
from pathlib import Path
from urllib.parse import urlparse

import asyncpg

from pgvector.asyncpg import register_vector

from config.settings import get_settings

logger = logging.getLogger(__name__)
_pool: asyncpg.Pool | None = None
_pool_lock: asyncio.Lock | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool, _pool_lock
    if _pool_lock is None:
        _pool_lock = asyncio.Lock()
    if _pool is None:
        async with _pool_lock:
            if _pool is None:
                _pool = await _create_pool()
    return _pool


async def _create_pool() -> asyncpg.Pool:
    settings = get_settings()
    parsed = urlparse(settings.database_url)
    use_ssl = "sslmode=require" in settings.database_url or parsed.port == 6432
    if use_ssl:
        yc_ca = Path("/usr/local/share/ca-certificates/YandexInternalRootCA.crt")
        ssl_param = ssl.create_default_context(
            cafile=str(yc_ca) if yc_ca.exists() else None,
        )
    else:
        ssl_param = False  # explicitly disable SSL (asyncpg defaults to "prefer")
    # Strip sslmode from DSN — asyncpg uses the ssl parameter instead
    dsn = settings.database_url.replace("?sslmode=require", "").replace("&sslmode=require", "")
    return await asyncpg.create_pool(
        dsn,
        ssl=ssl_param,
        statement_cache_size=settings.db_statement_cache_size,
        min_size=2,
        max_size=10,
        init=register_vector,
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

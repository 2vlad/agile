"""Gold standard: Repository + DTO pattern.

DTOs are @dataclass, named XRecord or XResult.
Repos are plain classes (no inheritance), use pool.acquire() context manager.
Serialize dicts with json.dumps before passing to DB.
"""
import json
from dataclasses import dataclass

from db.connection import get_pool


@dataclass
class ItemRecord:
    item_id: str
    name: str
    metadata: dict
    status: str


@dataclass
class SearchResult:
    item_id: str
    text: str
    score: float
    search_type: str


class ItemRepo:
    async def upsert(self, item: ItemRecord) -> None:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO items (item_id, name, metadata, status)
                   VALUES ($1, $2, $3, $4)
                   ON CONFLICT (item_id) DO UPDATE SET
                     name=EXCLUDED.name, metadata=EXCLUDED.metadata""",
                item.item_id,
                item.name,
                json.dumps(item.metadata),
                item.status,
            )

    async def get_by_id(self, item_id: str) -> ItemRecord | None:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM items WHERE item_id = $1", item_id
            )
            return ItemRecord(**dict(row)) if row else None

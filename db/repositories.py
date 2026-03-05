from dataclasses import dataclass
from typing import Any
import asyncpg
import json
import logging

from db.connection import get_pool

logger = logging.getLogger(__name__)


@dataclass
class DocumentRecord:
    doc_id: str
    filename: str
    format: str
    title: str | None
    content_hash: str
    status: str
    error: str | None = None


@dataclass
class ChunkRecord:
    chunk_id: str
    doc_id: str
    chunk_index: int
    total_chunks: int
    text: str
    metadata: dict
    embedding: list[float] | None = None


@dataclass
class SearchResult:
    chunk_id: str
    doc_id: str
    doc_title: str | None
    chunk_index: int
    total_chunks: int
    text: str
    metadata: dict
    score: float
    search_type: str  # 'vector' | 'fulltext'


class DocumentRepo:
    async def upsert(self, doc: DocumentRecord) -> None:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO documents (doc_id, filename, format, title, content_hash, status, error)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
                   ON CONFLICT (doc_id) DO UPDATE SET
                     filename=EXCLUDED.filename, format=EXCLUDED.format,
                     title=EXCLUDED.title, content_hash=EXCLUDED.content_hash,
                     status=EXCLUDED.status, error=EXCLUDED.error,
                     ingested_at=NOW()""",
                doc.doc_id,
                doc.filename,
                doc.format,
                doc.title,
                doc.content_hash,
                doc.status,
                doc.error,
            )

    async def get_by_hash(self, content_hash: str) -> DocumentRecord | None:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM documents WHERE content_hash = $1", content_hash
            )
            if row is None:
                return None
            data = dict(row)
            data.pop("ingested_at", None)
            return DocumentRecord(**data)

    async def get_by_id(self, doc_id: str) -> DocumentRecord | None:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM documents WHERE doc_id = $1", doc_id
            )
            if row is None:
                return None
            data = dict(row)
            data.pop("ingested_at", None)
            return DocumentRecord(**data)

    async def update_status(
        self, doc_id: str, status: str, error: str | None = None
    ) -> None:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE documents SET status=$1, error=$2 WHERE doc_id=$3",
                status,
                error,
                doc_id,
            )

    async def list_indexed(self) -> list[DocumentRecord]:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM documents WHERE status='indexed' ORDER BY filename"
            )
            results = []
            for r in rows:
                data = dict(r)
                data.pop("ingested_at", None)
                results.append(DocumentRecord(**data))
            return results


class ChunkRepo:
    async def bulk_insert(self, chunks: list[ChunkRecord]) -> None:
        if not chunks:
            return
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.executemany(
                """INSERT INTO chunks (chunk_id, doc_id, chunk_index, total_chunks, text, metadata, embedding)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
                   ON CONFLICT (doc_id, chunk_index) DO UPDATE SET
                     text=EXCLUDED.text, metadata=EXCLUDED.metadata, embedding=EXCLUDED.embedding""",
                [
                    (
                        c.chunk_id,
                        c.doc_id,
                        c.chunk_index,
                        c.total_chunks,
                        c.text,
                        json.dumps(c.metadata),
                        c.embedding,
                    )
                    for c in chunks
                ],
            )

    async def delete_by_doc(self, doc_id: str) -> None:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM chunks WHERE doc_id=$1", doc_id)

    async def search_vector(
        self, embedding: list[float], n_results: int = 5
    ) -> list[SearchResult]:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT c.chunk_id, c.doc_id, d.title as doc_title,
                          c.chunk_index, c.total_chunks, c.text, c.metadata,
                          1 - (c.embedding <=> $1::vector) as score
                   FROM chunks c
                   JOIN documents d ON c.doc_id = d.doc_id
                   WHERE c.embedding IS NOT NULL
                   ORDER BY c.embedding <=> $1::vector
                   LIMIT $2""",
                embedding,
                n_results,
            )
            return [
                SearchResult(
                    chunk_id=r["chunk_id"],
                    doc_id=r["doc_id"],
                    doc_title=r["doc_title"],
                    chunk_index=r["chunk_index"],
                    total_chunks=r["total_chunks"],
                    text=r["text"],
                    metadata=dict(r["metadata"]) if r["metadata"] else {},
                    score=float(r["score"]),
                    search_type="vector",
                )
                for r in rows
            ]

    async def search_fulltext(
        self, query: str, n_results: int = 5
    ) -> list[SearchResult]:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT c.chunk_id, c.doc_id, d.title as doc_title,
                          c.chunk_index, c.total_chunks, c.text, c.metadata,
                          ts_rank(c.tsv, plainto_tsquery('russian', $1)) as score
                   FROM chunks c
                   JOIN documents d ON c.doc_id = d.doc_id
                   WHERE c.tsv @@ plainto_tsquery('russian', $1)
                   ORDER BY score DESC
                   LIMIT $2""",
                query,
                n_results,
            )
            return [
                SearchResult(
                    chunk_id=r["chunk_id"],
                    doc_id=r["doc_id"],
                    doc_title=r["doc_title"],
                    chunk_index=r["chunk_index"],
                    total_chunks=r["total_chunks"],
                    text=r["text"],
                    metadata=dict(r["metadata"]) if r["metadata"] else {},
                    score=float(r["score"]),
                    search_type="fulltext",
                )
                for r in rows
            ]

    async def get_passage(
        self, doc_id: str, chunk_index: int, radius: int = 5
    ) -> list[dict]:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT chunk_index, text, metadata FROM chunks
                   WHERE doc_id=$1 AND chunk_index BETWEEN $2 AND $3
                   ORDER BY chunk_index""",
                doc_id,
                chunk_index - radius,
                chunk_index + radius,
            )
            return [dict(r) for r in rows]


class RequestRepo:
    async def log(
        self,
        request_id: str,
        user_id: int,
        username: str | None,
        query: str,
        answer: str | None,
        latency_ms: int | None,
        tools_used: list[dict],
    ) -> None:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO requests (request_id, user_id, username, query, answer, latency_ms, tools_used)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                request_id,
                user_id,
                username,
                query,
                answer,
                latency_ms,
                json.dumps(tools_used),
            )

    async def get_stats(self, days: int = 7) -> dict:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT COUNT(*) as total, COUNT(DISTINCT user_id) as unique_users,
                          AVG(latency_ms) as avg_latency,
                          COUNT(CASE WHEN answer IS NULL OR answer='' THEN 1 END) as errors
                   FROM requests
                   WHERE created_at >= NOW() - $1::interval""",
                f"{days} days",
            )
            return dict(row)

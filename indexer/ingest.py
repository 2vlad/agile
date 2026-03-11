"""Single-file ingestion — reusable by both CLI indexer and Telegram handler."""

import hashlib
import logging
from pathlib import Path

from config.settings import get_settings
from db.repositories import ChunkRecord, ChunkRepo, DocumentRecord, DocumentRepo
from indexer.chunker import chunk_text
from indexer.parsers import ParsedDocument, parse_file
from yandex.ai_studio import YandexAIStudio

logger = logging.getLogger(__name__)


def make_doc_id(filepath: Path) -> str:
    """Deterministic doc_id from filename + content hash prefix."""
    return hashlib.sha256(filepath.name.encode()).hexdigest()[:16]


async def ingest_file(
    filepath: Path,
    ai_client: YandexAIStudio,
    doc_id: str | None = None,
    on_progress: None = None,
) -> tuple[str, str, int]:
    """Parse, chunk, embed, and store a single file.

    Returns (status, title, chunk_count):
      - ("indexed", title, N) — success
      - ("skipped", title, 0) — already indexed or no content
    """
    settings = get_settings()
    doc_repo = DocumentRepo()
    chunk_repo = ChunkRepo()

    doc_id = doc_id or make_doc_id(filepath)

    # Parse
    parsed: ParsedDocument = parse_file(filepath)

    # Idempotency — skip if same content already indexed
    existing = await doc_repo.get_by_hash(parsed.content_hash)
    if existing and existing.status == "indexed":
        logger.info("Skipping %s (already indexed as %s)", filepath.name, existing.doc_id)
        return "skipped", existing.title or parsed.title, 0

    # Chunk
    chunks = chunk_text(
        parsed.text,
        chunk_size=settings.chunk_size,
        overlap=settings.chunk_overlap,
        doc_metadata={"filename": parsed.filename, "title": parsed.title},
    )

    if not chunks:
        await doc_repo.upsert(DocumentRecord(
            doc_id=doc_id,
            filename=parsed.filename,
            format=parsed.format,
            title=parsed.title,
            content_hash=parsed.content_hash,
            status="skipped",
            error="No chunks produced",
        ))
        return "skipped", parsed.title, 0

    # Embed
    chunk_texts = [c.text for c in chunks]
    embeddings = await ai_client.get_doc_embeddings_batch(chunk_texts)

    # Build records
    total_chunks = len(chunks)
    chunk_records = [
        ChunkRecord(
            chunk_id=f"{doc_id}_{c.chunk_index:04d}",
            doc_id=doc_id,
            chunk_index=c.chunk_index,
            total_chunks=total_chunks,
            text=c.text,
            metadata=c.metadata,
            embedding=embeddings[i],
        )
        for i, c in enumerate(chunks)
    ]

    # Store
    await doc_repo.upsert(DocumentRecord(
        doc_id=doc_id,
        filename=parsed.filename,
        format=parsed.format,
        title=parsed.title,
        content_hash=parsed.content_hash,
        status="indexed",
    ))
    await chunk_repo.delete_by_doc(doc_id)
    await chunk_repo.bulk_insert(chunk_records)

    logger.info("Indexed %s: %d chunks, doc_id=%s", filepath.name, total_chunks, doc_id)
    return "indexed", parsed.title, total_chunks

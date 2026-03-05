"""Indexer CLI entrypoint.

Walks the corpus directory, parses documents, chunks text,
generates embeddings, and stores everything in the database.

Usage:
    python -m indexer.main
"""

import asyncio
import hashlib
import logging
import time
from pathlib import Path

from config.settings import get_settings
from db.connection import close_pool, init_db
from db.repositories import ChunkRecord, ChunkRepo, DocumentRecord, DocumentRepo
from indexer.chunker import chunk_text
from indexer.parsers import ParsedDocument, SkippedDocument, parse_file
from yandex.ai_studio import YandexAIStudio

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".epub"}


def _make_doc_id(filepath: Path, corpus_dir: Path) -> str:
    rel = filepath.relative_to(corpus_dir)
    return hashlib.sha256(str(rel).encode()).hexdigest()[:16]


def _discover_files(corpus_dir: Path) -> list[Path]:
    """Walk corpus_dir and return all supported files sorted by name."""
    files = [
        p for p in corpus_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    files.sort(key=lambda p: p.name)
    return files


async def _process_file(
    filepath: Path,
    corpus_dir: Path,
    doc_repo: DocumentRepo,
    chunk_repo: ChunkRepo,
    ai: YandexAIStudio,
) -> str:
    """Process a single file through the full pipeline.

    Returns status string: 'indexed', 'skipped', or 'failed'.
    """
    doc_id = _make_doc_id(filepath, corpus_dir)

    # Parse
    parsed: ParsedDocument = parse_file(filepath)

    # Idempotency check
    existing = await doc_repo.get_by_hash(parsed.content_hash)
    if existing and existing.status in ("indexed", "skipped"):
        logger.info("Skipping %s (already %s)", filepath.name, existing.status)
        return "skipped"

    # Chunk
    settings = get_settings()
    chunks = chunk_text(
        parsed.text,
        chunk_size=settings.chunk_size,
        overlap=settings.chunk_overlap,
        doc_metadata={"filename": parsed.filename, "title": parsed.title},
    )

    if not chunks:
        logger.warning("No chunks produced for %s, marking skipped", filepath.name)
        await doc_repo.upsert(DocumentRecord(
            doc_id=doc_id,
            filename=parsed.filename,
            format=parsed.format,
            title=parsed.title,
            content_hash=parsed.content_hash,
            status="skipped",
            error="No chunks produced",
        ))
        return "skipped"

    # Embed
    chunk_texts = [c.text for c in chunks]
    embeddings = await ai.get_doc_embeddings_batch(chunk_texts)

    if len(embeddings) != len(chunks):
        raise RuntimeError(
            f"Embedding count mismatch for {filepath.name}: "
            f"got {len(embeddings)} embeddings for {len(chunks)} chunks"
        )

    # Build ChunkRecords
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

    # Store document + chunks (delete stale chunks first for clean re-index)
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

    logger.info(
        "Indexed %s: %d chunks, doc_id=%s",
        filepath.name, total_chunks, doc_id,
    )
    return "indexed"


async def main() -> None:
    """Run the full indexing pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    settings = get_settings()
    corpus_dir = Path(settings.corpus_dir).resolve()

    if not corpus_dir.is_dir():
        logger.error("Corpus directory does not exist: %s", corpus_dir)
        return

    files = _discover_files(corpus_dir)
    logger.info("Found %d files in %s", len(files), corpus_dir)

    if not files:
        logger.info("Nothing to index")
        return

    await init_db()

    ai = YandexAIStudio(
        api_key=settings.yc_api_key,
        folder_id=settings.yc_folder_id,
        llm_model=settings.llm_model,
        embed_doc_model=settings.embed_doc_model,
        embed_query_model=settings.embed_query_model,
        llm_base_url=settings.yc_llm_base_url,
        embeddings_url=settings.yc_embeddings_url,
    )

    doc_repo = DocumentRepo()
    chunk_repo = ChunkRepo()

    counts = {"indexed": 0, "skipped": 0, "failed": 0}
    start = time.monotonic()

    try:
        for filepath in files:
            try:
                status = await _process_file(
                    filepath, corpus_dir, doc_repo, chunk_repo, ai,
                )
                counts[status] += 1
            except SkippedDocument as exc:
                logger.warning("Skipped %s: %s", filepath.name, exc)
                doc_id = _make_doc_id(filepath, corpus_dir)
                await doc_repo.upsert(DocumentRecord(
                    doc_id=doc_id,
                    filename=filepath.name,
                    format=filepath.suffix.lstrip(".").lower(),
                    title=None,
                    content_hash="",
                    status="skipped",
                    error=str(exc),
                ))
                counts["skipped"] += 1
            except Exception as exc:
                logger.exception("Failed to process %s", filepath.name)
                doc_id = _make_doc_id(filepath, corpus_dir)
                await doc_repo.upsert(DocumentRecord(
                    doc_id=doc_id,
                    filename=filepath.name,
                    format=filepath.suffix.lstrip(".").lower(),
                    title=None,
                    content_hash="",
                    status="failed",
                    error=str(exc),
                ))
                counts["failed"] += 1

        elapsed = time.monotonic() - start
        summary = (
            f"Indexing complete: {counts['indexed']} indexed, "
            f"{counts['skipped']} skipped, {counts['failed']} failed. "
            f"Total time: {elapsed:.1f}s"
        )
        logger.info(summary)
    finally:
        await ai.close()
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())

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
from db.repositories import DocumentRecord, DocumentRepo
from indexer.ingest import ingest_file, make_doc_id
from indexer.parsers import SUPPORTED_EXTENSIONS, SkippedDocument
from yandex.ai_studio import YandexAIStudio

logger = logging.getLogger(__name__)


def _discover_files(corpus_dir: Path) -> list[Path]:
    """Walk corpus_dir and return all supported files sorted by name."""
    files = [
        p for p in corpus_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    files.sort(key=lambda p: p.name)
    return files


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

    counts = {"indexed": 0, "skipped": 0, "failed": 0}
    start = time.monotonic()

    try:
        for filepath in files:
            try:
                status, title, chunk_count = await ingest_file(filepath, ai)
                counts[status] += 1
            except SkippedDocument as exc:
                doc_id = make_doc_id(filepath)
                logger.warning("Skipped %s: %s", filepath.name, exc)
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
            except Exception:
                logger.exception("Failed to process %s", filepath.name)
                doc_id = make_doc_id(filepath)
                await doc_repo.upsert(DocumentRecord(
                    doc_id=doc_id,
                    filename=filepath.name,
                    format=filepath.suffix.lstrip(".").lower(),
                    title=None,
                    content_hash="",
                    status="failed",
                    error="processing error",
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

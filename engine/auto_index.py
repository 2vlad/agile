"""Auto-index corpus/ on startup — index new or changed files."""

import hashlib
import logging
from pathlib import Path

from config.settings import get_settings
from db.repositories import DocumentRepo
from engine.embeddings.base import EmbeddingClient
from indexer.ingest import ingest_file
from indexer.parsers import SUPPORTED_EXTENSIONS, SkippedDocument

logger = logging.getLogger(__name__)


def _discover_files(corpus_dir: Path) -> list[Path]:
    return sorted(
        (p for p in corpus_dir.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS),
        key=lambda p: p.name,
    )


async def auto_index_corpus(embed_client: EmbeddingClient) -> None:
    """Check corpus/ for new or changed files and index them."""
    settings = get_settings()
    corpus_dir = Path(settings.corpus_dir)
    if not corpus_dir.is_dir():
        logger.info("No corpus directory at %s, skipping auto-index", corpus_dir)
        return

    files = _discover_files(corpus_dir)
    if not files:
        logger.info("No files in %s", corpus_dir)
        return

    doc_repo = DocumentRepo()
    indexed, skipped = 0, 0

    for filepath in files:
        content_hash = hashlib.sha256(filepath.read_bytes()).hexdigest()
        existing = await doc_repo.get_by_hash(content_hash)
        if existing and existing.status == "indexed":
            skipped += 1
            continue

        try:
            status, title, chunks = await ingest_file(filepath, embed_client)
            if status == "indexed":
                indexed += 1
                logger.info("Auto-indexed: %s (%d chunks)", title, chunks)
            else:
                skipped += 1
        except SkippedDocument as exc:
            logger.warning("Skipped %s: %s", filepath.name, exc)
            skipped += 1
        except Exception:
            logger.exception("Failed to auto-index %s", filepath.name)

    if indexed:
        logger.info("Auto-index complete: %d new, %d skipped", indexed, skipped)
    else:
        logger.info("Auto-index: all %d files already indexed", skipped)

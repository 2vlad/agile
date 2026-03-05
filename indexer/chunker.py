import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Sentence boundary pattern for Russian + English text
_SENTENCE_SPLIT = re.compile(r'(?<=[.!?…»])\s+')


@dataclass
class Chunk:
    chunk_index: int
    text: str
    metadata: dict = field(default_factory=dict)


def chunk_text(
    text: str,
    chunk_size: int = 1200,
    overlap: int = 200,
    doc_metadata: dict | None = None,
) -> list[Chunk]:
    """Split text into overlapping chunks at sentence boundaries.

    Splitting priority: sentence boundary -> paragraph -> newline -> space
    Skips chunks shorter than 50 characters.
    """
    if not text.strip():
        return []

    doc_metadata = doc_metadata or {}

    # Split into sentences first
    sentences = _SENTENCE_SPLIT.split(text)

    chunks: list[Chunk] = []
    current_parts: list[str] = []
    current_len: int = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        sentence_len = len(sentence)

        # If a single sentence is larger than chunk_size, split it further
        if sentence_len > chunk_size:
            # Flush current buffer first
            if current_parts:
                _flush_chunk(chunks, current_parts, current_len, doc_metadata)
                # Keep overlap
                current_parts, current_len = _apply_overlap(current_parts, overlap)

            # Split the long sentence by paragraph, then newline, then space
            sub_sentences = _split_long(sentence, chunk_size)
            for sub in sub_sentences:
                sub_len = len(sub)
                if current_len + sub_len > chunk_size and current_parts:
                    _flush_chunk(chunks, current_parts, current_len, doc_metadata)
                    current_parts, current_len = _apply_overlap(current_parts, overlap)
                current_parts.append(sub)
                current_len += sub_len + 1
            continue

        if current_len + sentence_len > chunk_size and current_parts:
            _flush_chunk(chunks, current_parts, current_len, doc_metadata)
            current_parts, current_len = _apply_overlap(current_parts, overlap)

        current_parts.append(sentence)
        current_len += sentence_len + 1

    # Flush remaining
    if current_parts:
        _flush_chunk(chunks, current_parts, current_len, doc_metadata)

    # Re-index and filter short chunks
    result = [
        Chunk(chunk_index=i, text=c.text, metadata=c.metadata)
        for i, c in enumerate(chunks)
        if len(c.text) >= 50
    ]
    logger.debug(f"Chunked into {len(result)} chunks")
    return result


def _flush_chunk(chunks: list[Chunk], parts: list[str], length: int,
                 doc_metadata: dict) -> None:
    text = " ".join(parts).strip()
    if len(text) >= 50:
        chunks.append(Chunk(
            chunk_index=len(chunks),
            text=text,
            metadata=dict(doc_metadata),
        ))


def _apply_overlap(parts: list[str], overlap: int) -> tuple[list[str], int]:
    """Keep trailing sentences until their total length is ~overlap chars."""
    kept: list[str] = []
    total = 0
    for part in reversed(parts):
        if total + len(part) > overlap:
            break
        kept.insert(0, part)
        total += len(part) + 1
    return kept, total


def _split_long(text: str, chunk_size: int) -> list[str]:
    """Split a sentence longer than chunk_size by paragraph/newline/space."""
    for sep in ("\n\n", "\n", " "):
        if sep in text:
            parts = text.split(sep)
            result = []
            current = ""
            for part in parts:
                if len(current) + len(part) + len(sep) <= chunk_size:
                    current = (current + sep + part).lstrip(sep)
                else:
                    if current:
                        result.append(current)
                    current = part
            if current:
                result.append(current)
            return result
    # No separator found: hard split
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

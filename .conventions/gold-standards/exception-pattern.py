"""Gold standard: Domain exceptions + dataclass output + dispatcher.

Domain-specific Exception subclass for skippable/expected errors.
@dataclass output types with __post_init__ for computed fields.
Dispatcher function selects handler by type/extension.
"""
import hashlib
from dataclasses import dataclass, field


class SkippedItem(Exception):
    """Raised when an item cannot be processed (expected, non-fatal)."""


@dataclass
class ProcessedItem:
    name: str
    content: str
    metadata: dict = field(default_factory=dict)
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.content_hash:
            self.content_hash = hashlib.sha256(self.content.encode()).hexdigest()


def process(filepath: Path) -> ProcessedItem:
    """Dispatch to correct handler based on file extension."""
    ext = filepath.suffix.lower()
    handlers = {".txt": process_txt, ".pdf": process_pdf}
    handler = handlers.get(ext)
    if handler is None:
        raise ValueError(f"Unsupported format: {ext}")
    return handler(filepath)

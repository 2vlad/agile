import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class SkippedDocument(Exception):
    """Raised when a document cannot be meaningfully parsed (e.g. scan-only PDF)."""


@dataclass
class ParsedDocument:
    filename: str
    format: str          # 'pdf' | 'txt' | 'epub'
    title: str
    text: str
    metadata: dict = field(default_factory=dict)
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.content_hash:
            self.content_hash = hashlib.sha256(self.text.encode()).hexdigest()


def parse_file(filepath: Path) -> ParsedDocument:
    """Dispatch to correct parser based on file extension."""
    ext = filepath.suffix.lower()
    if ext == ".txt":
        return parse_txt(filepath)
    elif ext == ".pdf":
        return parse_pdf(filepath)
    elif ext == ".epub":
        return parse_epub(filepath)
    else:
        raise ValueError(f"Unsupported file format: {ext}")


def parse_txt(filepath: Path) -> ParsedDocument:
    """Parse a plain text file. Try UTF-8 then cp1251 (common for Russian texts)."""
    raw = filepath.read_bytes()
    content_hash = hashlib.sha256(raw).hexdigest()

    text = None
    for encoding in ("utf-8", "cp1251", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if text is None:
        raise ValueError(f"Cannot decode {filepath.name}")

    return ParsedDocument(
        filename=filepath.name,
        format="txt",
        title=filepath.stem.replace("_", " ").title(),
        text=text.strip(),
        content_hash=content_hash,
    )


def parse_pdf(filepath: Path) -> ParsedDocument:
    """Parse a text-based PDF page by page using PyMuPDF.

    Raises SkippedDocument if the PDF appears to be a scan (no extractable text).
    """
    content_hash = hashlib.sha256(filepath.read_bytes()).hexdigest()

    with fitz.open(str(filepath)) as doc:
        total_pages = doc.page_count
        meta = doc.metadata or {}

        pages_text: list[str] = []
        pages_with_text = 0

        for page_num, page in enumerate(doc, start=1):
            page_text = page.get_text("text").strip()
            if page_text:
                pages_with_text += 1
                pages_text.append(f"[Страница {page_num}]\n{page_text}")

    if pages_with_text == 0:
        raise SkippedDocument(f"{filepath.name}: no extractable text (likely a scan)")

    # Extract title from PDF metadata, fallback to filename
    title = (meta.get("title") or "").strip() or filepath.stem.replace("_", " ").title()

    text = "\n\n".join(pages_text)
    return ParsedDocument(
        filename=filepath.name,
        format="pdf",
        title=title,
        text=text,
        metadata={"total_pages": total_pages},
        content_hash=content_hash,
    )


def parse_epub(filepath: Path) -> ParsedDocument:
    """Parse an EPUB file, extracting text from HTML spine items chapter by chapter."""
    content_hash = hashlib.sha256(filepath.read_bytes()).hexdigest()

    book = epub.read_epub(str(filepath), options={"ignore_ncx": True})

    # Extract title from EPUB metadata
    title_meta = book.get_metadata("DC", "title")
    title = title_meta[0][0] if title_meta else filepath.stem.replace("_", " ").title()

    chapters: list[str] = []
    chapter_titles: list[str] = []

    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")

        # Extract chapter title from headings
        heading = soup.find(["h1", "h2", "h3"])
        chapter_title = heading.get_text(strip=True) if heading else ""

        # Remove scripts and styles
        for tag in soup(["script", "style", "head"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        text = "\n".join(line for line in text.splitlines() if line.strip())

        if len(text) > 100:  # Skip nearly-empty chapters
            if chapter_title:
                chapters.append(f"[{chapter_title}]\n{text}")
                chapter_titles.append(chapter_title)
            else:
                chapters.append(text)

    if not chapters:
        raise SkippedDocument(f"{filepath.name}: no text content found in EPUB")

    full_text = "\n\n".join(chapters)
    return ParsedDocument(
        filename=filepath.name,
        format="epub",
        title=title,
        text=full_text,
        metadata={"chapters": chapter_titles, "chapter_count": len(chapters)},
        content_hash=content_hash,
    )

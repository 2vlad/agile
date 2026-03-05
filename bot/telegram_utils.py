import re


def clean_html(text: str) -> str:
    """Remove markdown artifacts, keep only valid Telegram HTML tags."""
    # Remove markdown headers
    text = re.sub(r"#{1,6}\s*", "", text)
    # Bold markdown **text** -> <b>text</b>
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    # Double-underscore markdown __text__ -> <i>text</i>
    text = re.sub(r"__(.+?)__", r"<i>\1</i>", text)
    # Single star *text* -> <i>text</i>
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
    # Backtick `code` -> <code>code</code>
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    # Strip any HTML tags except allowed ones
    allowed = re.compile(r"</?(?:b|i|code)>")
    parts: list[str] = []
    last = 0
    for m in re.finditer(r"<[^>]+>", text):
        parts.append(escape_html(text[last : m.start()]))
        tag = m.group()
        if allowed.fullmatch(tag):
            parts.append(tag)
        # else: drop the tag
        last = m.end()
    parts.append(escape_html(text[last:]))
    return "".join(parts)


def escape_html(text: str) -> str:
    """Escape HTML special chars outside of tags."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def split_html_message(text: str, max_len: int = 4000) -> list[str]:
    """Split text into chunks that fit Telegram message limits.

    Splits by paragraphs first, then lines, then spaces.
    Never breaks inside HTML tags.
    """
    if not text:
        return []
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= max_len:
            chunks.append(remaining)
            break

        # Find a split point within max_len
        split_at = _find_split(remaining, max_len)
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip("\n")

    return [c for c in chunks if c.strip()]


def _find_split(text: str, max_len: int) -> int:
    """Find the best split point within max_len chars."""
    segment = text[:max_len]

    # Try splitting at paragraph boundary
    idx = segment.rfind("\n\n")
    if idx > 0:
        return idx + 2

    # Try splitting at line boundary
    idx = segment.rfind("\n")
    if idx > 0:
        return idx + 1

    # Try splitting at space
    idx = segment.rfind(" ")
    if idx > 0:
        return idx + 1

    # Last resort: split at max_len, but avoid breaking inside HTML tags
    tag_match = re.search(r"<[^>]*$", segment)
    if tag_match:
        return tag_match.start()

    return max_len

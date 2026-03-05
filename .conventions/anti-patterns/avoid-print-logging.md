# Anti-Pattern: print() Instead of Logging

## BAD

```python
def parse_file(filepath):
    print(f"Parsing {filepath}...")
    try:
        result = do_parse(filepath)
        print(f"Done: {len(result.text)} chars")
        return result
    except Exception as e:
        print(f"ERROR: {e}")
        raise
```

## GOOD

```python
import logging

logger = logging.getLogger(__name__)

def parse_file(filepath):
    logger.info("Parsing %s", filepath)
    try:
        result = do_parse(filepath)
        logger.debug("Parsed %s: %d chars", filepath, len(result.text))
        return result
    except Exception:
        logger.exception("Failed to parse %s", filepath)
        raise
```

## Rule
- Every module defines `logger = logging.getLogger(__name__)` at the top.
- Use `logger.debug` for verbose/tracing output.
- Use `logger.info` for operational milestones.
- Use `logger.warning` for recoverable issues.
- Use `logger.exception` inside `except` blocks (auto-attaches traceback).
- Never use `print()` for operational output.

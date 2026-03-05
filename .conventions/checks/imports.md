# Import Conventions

## Settings Access
- Always use `from config.settings import get_settings` then `settings = get_settings()`
- Never import `Settings` class directly for instantiation

## DB Pool Access
- Always use `from db.connection import get_pool` then `pool = await get_pool()`
- Never import `_pool` directly

## No Hardcoded Values
- URLs, tokens, model names, thresholds belong in `Settings`
- Non-settings modules read config via `get_settings()`

## Import Order
1. Standard library (`import asyncio`, `import json`, `import logging`)
2. Third-party (`import httpx`, `from openai import AsyncOpenAI`)
3. Local (`from config.settings import get_settings`, `from db.connection import get_pool`)

## Logging
- Every module: `logger = logging.getLogger(__name__)` at module level
- Use `logger.info/debug/warning/exception` — never `print()`

# Naming Conventions

## Files
- All Python files use `snake_case.py`

## Classes
- PascalCase: `DocumentRepo`, `YandexAIStudio`, `SearchResult`

## Functions and Methods
- snake_case: `get_settings()`, `parse_file()`, `search_corpus()`
- Use `async` for any function performing IO (database, network, file reads)

## DTOs (Data Transfer Objects)
- Always `@dataclass`
- Name pattern: `XRecord` for DB-mapped entities, `XResult` for query/search outputs
- Examples: `DocumentRecord`, `ChunkRecord`, `SearchResult`, `AgentResult`

## Singletons (module-level state)
- Prefixed with underscore: `_pool`, `_pool_lock`, `_history`
- Accessed via getter function: `get_pool()`, `get_settings()`

## Constants
- UPPER_CASE: `EMBEDDING_DIM`, `TOOL_RESULT_MAX_CHARS`, `TOOL_SCHEMAS`

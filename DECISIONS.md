# Architecture Decisions — feature-monograph-bot

## ADR-1: Yandex Embeddings — custom httpx client

**Decision**: Use a custom httpx client for the Yandex embeddings endpoint, NOT the openai SDK.

**Context**: The Yandex embeddings REST API at `https://llm.api.cloud.yandex.net/foundationModels/v1/textEmbedding` uses a different request/response format than OpenAI's `/v1/embeddings`. The chat completions endpoint at `https://ai.api.cloud.yandex.net/v1` is OpenAI-compatible and can use the openai SDK.

**Consequence**: Task #5 implements two separate clients — openai SDK for LLM chat, httpx for embeddings.

---

## ADR-2: pgvector dimension — 256 explicit

**Decision**: Use `vector(256)` explicitly in the PostgreSQL schema.

**Context**: Yandex text-search-doc/query embedding models output 256-dimensional vectors. A dimension mismatch causes silent failures in vector similarity search.

**Consequence**: Task #3 schema uses `vector(256)`. Task #5 asserts embedding output dimension equals 256 on first call.

---

## ADR-3: asyncpg SSL — ssl.create_default_context()

**Decision**: Pass `ssl=ssl.create_default_context()` to asyncpg connection, not `sslmode=require` in the DSN.

**Context**: asyncpg handles SSL differently than psycopg2. It requires an `ssl.SSLContext` object or `ssl=True`, not the `sslmode` DSN parameter. Yandex Managed PostgreSQL requires SSL.

**Consequence**: Task #3 connection pool creation uses explicit SSL context parameter.

---

## ADR-4: asyncpg — statement_cache_size=0

**Decision**: Configure asyncpg pool with `statement_cache_size=0`.

**Context**: Port 6432 indicates PgBouncer in front of PostgreSQL. PgBouncer in transaction pooling mode is incompatible with asyncpg's default prepared statement caching, causing "prepared statement does not exist" errors.

**Consequence**: Task #3 disables prepared statement cache in pool configuration.

---

## ADR-5: Entity extraction — out of scope for MVP

**Decision**: No knowledge graph or entity extraction. RAG-only architecture.

**Context**: The reference architecture includes a knowledge graph (directors, persons, films, concepts, mentions tables). For this MVP over monographs on agile/organizational design, pure semantic search via pgvector is sufficient.

**Consequence**: No entity tables in schema. Tools are `search_corpus` and `get_passage` only. Can be added in a future iteration.

---

## ADR-6: Conversation history — in-memory dict

**Decision**: Store conversation history in an in-memory dict, no database persistence.

**Context**: For MVP scale (single instance, moderate traffic), in-memory storage with TTL-based cleanup is simpler and sufficient. Dialog memory resets on service restart.

**Consequence**: No conversations/messages table in the database schema. Task #9 uses in-memory dict with TTL expiration.

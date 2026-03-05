CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    format TEXT NOT NULL CHECK (format IN ('pdf', 'txt', 'epub')),
    title TEXT,
    ingested_at TIMESTAMPTZ DEFAULT NOW(),
    content_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('indexed', 'failed', 'skipped', 'pending')),
    error TEXT
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    total_chunks INTEGER NOT NULL,
    text TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    embedding vector(256),
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('russian', text)) STORED,
    UNIQUE(doc_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_chunks_tsv ON chunks USING gin(tsv);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id);

CREATE TABLE IF NOT EXISTS requests (
    request_id TEXT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    username TEXT,
    query TEXT NOT NULL,
    answer TEXT,
    latency_ms INTEGER,
    tools_used JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

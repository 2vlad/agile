# Team State — feature-monograph-bot

## Recovery Instructions
Read this file if context was compacted. Your role in Phase 2:
- Listen for DONE/STUCK/QUESTION from coders
- DO NOT read code, run checks, or notify reviewers (coders do that directly)
- Update this file after each event

## Phase: EXECUTION
## Complexity: COMPLEX

## Team Roster
- tech-lead: ACTIVE
- security-reviewer: ACTIVE
- logic-reviewer: ACTIVE
- quality-reviewer: ACTIVE

## Yandex API Constants (for coder prompts)
- LLM base_url: https://ai.api.cloud.yandex.net/v1
- Auth: Authorization: Bearer {YC_API_KEY} + OpenAI-Project: {YC_FOLDER_ID} header
- Use openai Python SDK with custom base_url
- Embeddings REST: https://llm.api.cloud.yandex.net/foundationModels/v1/textEmbedding
- LLM model: gpt://{folder_id}/yandexgpt/latest
- Embed doc model: emb://{folder_id}/text-search-doc/latest
- Embed query model: emb://{folder_id}/text-search-query/latest
- Embedding dimensions: 256
- PG host: c-{cluster_id}.rw.mdb.yandexcloud.net, port: 6432, sslmode=require
- Secrets: env vars (Lockbox-injected at deploy time)

## Tasks
- #2: Project scaffolding — COMPLETED
- #3: Database layer — IN_PROGRESS(coder-2)
- #4: Document parsers — IN_PROGRESS(coder-3)
- #5: Chunking + AI Studio client — IN_PROGRESS(coder-4)
- #6: Indexer CLI — UNASSIGNED (blocked by #3,4,5)
- #7: RAG search tools — UNASSIGNED (blocked by #3,5)
- #8: ReAct agent — UNASSIGNED (blocked by #5,7)
- #9: Telegram bot — UNASSIGNED (blocked by #3,8)
- #10: Deployment — UNASSIGNED (blocked by #9)
- #11: Conventions — UNASSIGNED (blocked by all)

## Active Coders: 3 (max: 3)

## Events Log
- [done] coder-1 completed task #2 (commit: feat: project scaffolding)
- [spawn] coder-2 started task #3
- [spawn] coder-3 started task #4
- [spawn] coder-4 started task #5

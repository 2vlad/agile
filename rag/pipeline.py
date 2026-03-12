"""Pipeline RAG: search → single LLM call → structured answer.

Simpler and faster than the ReAct agent — no tool calling needed.
"""

import logging
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from config.settings import get_settings
from observability import get_langfuse, flush as lf_flush
from rag.prompts import get_system_prompt
from engine.embeddings.base import EmbeddingClient
from engine.llm.base import LLMClient
from rag.tools import search_corpus

logger = logging.getLogger(__name__)

CONTEXT_MAX_CHARS = 12_000


def _strip_sources(answer: str) -> str:
    """Remove any 'Источники:' footer the LLM may generate."""
    return re.sub(r"\n*\s*Источники:.*", "", answer, flags=re.DOTALL).rstrip()


@dataclass
class PipelineResult:
    answer: str
    sources: list[str] = field(default_factory=list)
    chunks_found: int = 0
    latency_ms: int = 0


def _format_context(search_results: list[dict]) -> str:
    """Format search results into a context block for the LLM."""
    if not search_results:
        return "(ничего не найдено)"

    parts: list[str] = []
    total = 0
    for i, r in enumerate(search_results, 1):
        text = r.get("expanded_text") or r.get("text", "")
        chunk = f"[Фрагмент {i}]\n{text}"
        if total + len(chunk) > CONTEXT_MAX_CHARS:
            break
        parts.append(chunk)
        total += len(chunk)
    return "\n\n---\n\n".join(parts)


async def run_pipeline(
    query: str,
    user_id: int,
    history: list[dict],
    llm_client: LLMClient,
    embed_client: EmbeddingClient,
    doc_titles: list[str] | None = None,
    on_status: Callable[[str], Awaitable[None]] | None = None,
) -> PipelineResult:
    """Run pipeline RAG: search corpus, then generate answer in one LLM call."""
    settings = get_settings()
    start = time.monotonic()
    langfuse = get_langfuse()

    # Step 1: Search
    if on_status:
        await on_status("\U0001f50d Ищу в монографиях...")

    search_results = await search_corpus(
        query=query,
        n_results=settings.max_search_results,
        embed_client=embed_client,
    )

    logger.info("Search returned %d results for user %s", len(search_results), user_id)

    # Track sources
    sources: dict[str, str] = {}
    for item in search_results:
        if isinstance(item, dict) and item.get("doc_id") and item.get("doc_title"):
            sources[item["doc_id"]] = item["doc_title"]

    # Step 2: Build prompt with context
    if on_status:
        await on_status("\U0001f4ac Формулирую ответ...")

    context_block = _format_context(search_results)
    system_prompt = get_system_prompt(doc_titles or [])

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        *history,
        {
            "role": "user",
            "content": (
                f"{query}\n\n"
                f"---\nНайденные фрагменты из базы знаний:\n\n{context_block}"
            ),
        },
    ]

    # Step 3: Generate answer
    response = await llm_client.chat_completion(
        messages=messages,
        tools=None,
        max_tokens=4000,
    )
    raw_content = response.choices[0].message.content or ""

    elapsed = int((time.monotonic() - start) * 1000)
    answer = _strip_sources(raw_content)

    logger.info(
        "Pipeline finished in %dms, %d chunks, %d sources, answer_len=%d",
        elapsed, len(search_results), len(sources), len(answer),
    )

    # Step 4: Send trace to Langfuse
    if langfuse:
        try:
            chunks_summary = [
                {
                    "doc_title": r.get("doc_title", ""),
                    "chunk_index": r.get("chunk_index"),
                    "score": round(r.get("score", 0), 4),
                    "text_preview": (r.get("text") or "")[:200],
                }
                for r in search_results
            ]

            with langfuse.start_as_current_span(name="pipeline-rag") as span:
                span.update(
                    input={"query": query, "history_len": len(history)},
                    output={
                        "answer": answer,
                        "latency_ms": elapsed,
                        "sources": list(sources.values()),
                        "chunks_found": len(search_results),
                    },
                    metadata={
                        "user_id": str(user_id),
                        "search_results": chunks_summary,
                        "system_prompt": system_prompt[:500],
                        "context_chars": len(context_block),
                        "message_count": len(messages),
                    },
                )

                with langfuse.start_as_current_generation(
                    name="llm-generate",
                ) as gen:
                    gen.update(
                        input=messages,
                        output=raw_content,
                    )

            lf_flush()
        except Exception:
            logger.warning("Failed to send Langfuse trace", exc_info=True)

    return PipelineResult(
        answer=answer,
        sources=list(sources.values()),
        chunks_found=len(search_results),
        latency_ms=elapsed,
    )

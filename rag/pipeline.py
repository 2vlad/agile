"""Pipeline RAG: search → single LLM call → structured answer.

Simpler and faster than the ReAct agent — no tool calling needed.
"""

import json
import logging
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from config.settings import get_settings
from observability import create_trace, flush as lf_flush
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

    trace = create_trace(
        name="pipeline-rag",
        user_id=str(user_id),
        input={"query": query, "history_len": len(history)},
        metadata={"doc_titles_count": len(doc_titles or [])},
        tags=["rag", "pipeline"],
    )

    # Step 1: Search
    if on_status:
        await on_status("\U0001f50d Ищу в монографиях...")

    search_span = trace.span(name="search", input={"query": query, "n_results": settings.max_search_results}) if trace else None
    try:
        search_results = await search_corpus(
            query=query,
            n_results=settings.max_search_results,
            embed_client=embed_client,
        )
        if search_span:
            chunks_summary = [
                {
                    "doc_title": r.get("doc_title", ""),
                    "chunk_index": r.get("chunk_index"),
                    "score": round(r.get("score", 0), 4),
                    "text_preview": (r.get("text") or "")[:200],
                }
                for r in search_results
            ]
            search_span.end(output={"count": len(search_results), "chunks": chunks_summary})
    except Exception:
        if search_span:
            search_span.end(output={"error": "search failed"}, level="ERROR")
        logger.exception("Search failed for user %s", user_id)
        raise

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

    # Step 3: Generate answer (single LLM call, no tools)
    gen_span = trace.span(
        name="llm-generate",
        input={
            "system_prompt": system_prompt,
            "history": history,
            "user_message": query,
            "context_chars": len(context_block),
            "message_count": len(messages),
        },
    ) if trace else None
    try:
        response = await llm_client.chat_completion(
            messages=messages,
            tools=None,
            max_tokens=4000,
        )
        raw_content = response.choices[0].message.content or ""
        if gen_span:
            gen_span.end(output={"answer": raw_content})
    except Exception:
        if gen_span:
            gen_span.end(output={"error": "LLM call failed"}, level="ERROR")
        logger.exception("LLM call failed for user %s", user_id)
        raise

    elapsed = int((time.monotonic() - start) * 1000)
    answer = _strip_sources(raw_content)

    logger.info(
        "Pipeline finished in %dms, %d chunks, %d sources, answer_len=%d",
        elapsed, len(search_results), len(sources), len(answer),
    )

    if trace:
        trace.update(output={
            "answer": answer,
            "latency_ms": elapsed,
            "sources": list(sources.values()),
            "chunks_found": len(search_results),
        })
        lf_flush()

    return PipelineResult(
        answer=answer,
        sources=list(sources.values()),
        chunks_found=len(search_results),
        latency_ms=elapsed,
    )

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

    try:
        if langfuse:
            with langfuse.start_as_current_span(name="pipeline-rag") as trace_span:
                trace_span.update(
                    input={"query": query, "history_len": len(history)},
                    metadata={"user_id": str(user_id), "doc_titles_count": len(doc_titles or [])},
                )
                result = await _run_pipeline_inner(
                    query, user_id, history, llm_client, embed_client,
                    doc_titles, on_status, settings, start, langfuse, trace_span,
                )
            lf_flush()
            return result
        else:
            return await _run_pipeline_inner(
                query, user_id, history, llm_client, embed_client,
                doc_titles, on_status, settings, start, None, None,
            )
    except Exception:
        logger.exception("Pipeline failed for user %s", user_id)
        raise


async def _run_pipeline_inner(
    query: str,
    user_id: int,
    history: list[dict],
    llm_client: LLMClient,
    embed_client: EmbeddingClient,
    doc_titles: list[str] | None,
    on_status: Callable[[str], Awaitable[None]] | None,
    settings: Any,
    start: float,
    langfuse: Any,
    trace_span: Any,
) -> PipelineResult:
    """Inner pipeline logic, optionally wrapped in a Langfuse span."""

    # Search
    search_results = await search_corpus(
        query=query,
        n_results=settings.max_search_results,
        embed_client=embed_client,
    )

    if langfuse and trace_span:
        with langfuse.start_as_current_observation(name="search", as_type="span") as search_obs:
            chunks_summary = [
                {
                    "doc_title": r.get("doc_title", ""),
                    "chunk_index": r.get("chunk_index"),
                    "score": round(r.get("score", 0), 4),
                    "text_preview": (r.get("text") or "")[:200],
                }
                for r in search_results
            ]
            search_obs.update(
                input={"query": query, "n_results": settings.max_search_results},
                output={"count": len(search_results), "chunks": chunks_summary},
            )

    logger.info("Search returned %d results for user %s", len(search_results), user_id)

    # Track sources
    sources: dict[str, str] = {}
    for item in search_results:
        if isinstance(item, dict) and item.get("doc_id") and item.get("doc_title"):
            sources[item["doc_id"]] = item["doc_title"]

    # Build prompt with context
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

    # Generate answer
    response = await llm_client.chat_completion(
        messages=messages,
        tools=None,
        max_tokens=4000,
    )
    raw_content = response.choices[0].message.content or ""

    if langfuse and trace_span:
        with langfuse.start_as_current_observation(
            name="llm-generate",
            as_type="generation",
        ) as gen_obs:
            gen_obs.update(
                input={
                    "system_prompt": system_prompt,
                    "history": history,
                    "user_message": query,
                    "context_chars": len(context_block),
                    "message_count": len(messages),
                },
                output={"answer": raw_content},
            )

    elapsed = int((time.monotonic() - start) * 1000)
    answer = _strip_sources(raw_content)

    logger.info(
        "Pipeline finished in %dms, %d chunks, %d sources, answer_len=%d",
        elapsed, len(search_results), len(sources), len(answer),
    )

    if trace_span:
        trace_span.update(output={
            "answer": answer,
            "latency_ms": elapsed,
            "sources": list(sources.values()),
            "chunks_found": len(search_results),
        })

    return PipelineResult(
        answer=answer,
        sources=list(sources.values()),
        chunks_found=len(search_results),
        latency_ms=elapsed,
    )

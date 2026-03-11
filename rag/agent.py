import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from config.settings import get_settings
from observability import create_trace, flush as lf_flush
from rag.prompts import get_system_prompt
from rag.tools import TOOL_SCHEMAS, get_passage, search_corpus
from yandex.ai_studio import YandexAIStudio

logger = logging.getLogger(__name__)

TOOL_RESULT_MAX_CHARS = 12_000


def _strip_sources(answer: str) -> str:
    """Remove any 'Источники:' footer the LLM may generate."""
    import re
    return re.sub(r"\n*\s*Источники:.*", "", answer, flags=re.DOTALL).rstrip()


@dataclass
class AgentResult:
    answer: str
    tools_used: list[dict] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    latency_ms: int = 0


async def _execute_tool(
    name: str,
    arguments: dict[str, Any],
    ai_client: YandexAIStudio | None = None,
) -> tuple[str, Any]:
    """Dispatch a tool call and return (truncated JSON string, raw result)."""
    if name == "search_corpus":
        result = await search_corpus(
            query=arguments["query"],
            n_results=arguments.get("n_results", 5),
            ai_client=ai_client,
        )
    elif name == "get_passage":
        result = await get_passage(
            doc_id=arguments["doc_id"],
            chunk_index=arguments["chunk_index"],
            radius=arguments.get("radius", 3),
        )
    else:
        result = {"error": f"Unknown tool: {name}"}

    text = json.dumps(result, ensure_ascii=False)
    if len(text) > TOOL_RESULT_MAX_CHARS:
        text = text[:TOOL_RESULT_MAX_CHARS] + "..."
    return text, result


async def run_agent(
    query: str,
    user_id: int,
    history: list[dict],
    ai_client: YandexAIStudio,
    doc_titles: list[str] | None = None,
    on_status: Callable[[str], Awaitable[None]] | None = None,
) -> AgentResult:
    """Run the ReAct agent loop: search, reason, answer."""
    settings = get_settings()
    start = time.monotonic()

    # Langfuse trace for the entire agent run
    trace = create_trace(
        name="agent-run",
        user_id=str(user_id),
        metadata={"query": query[:500]},
        tags=["rag", "agent"],
    )

    system_prompt = get_system_prompt(doc_titles or [], max_iterations=settings.max_agent_iterations)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": query},
    ]

    tools_used: list[dict] = []
    sources: dict[str, str] = {}  # doc_id -> doc_title

    for iteration in range(settings.max_agent_iterations):
        logger.info("Agent iteration %d/%d for user %s", iteration + 1, settings.max_agent_iterations, user_id)

        generation = trace.span(name=f"llm-iteration-{iteration+1}", input={"message_count": len(messages)}) if trace else None
        # On last allowed iteration, stop offering tools to force a final answer
        offer_tools = TOOL_SCHEMAS if iteration < settings.max_agent_iterations - 1 else None
        try:
            response = await ai_client.chat_completion(messages, tools=offer_tools)
        except Exception:
            if generation:
                generation.end(output={"error": "LLM call failed"}, level="ERROR")
            logger.exception("LLM call failed on iteration %d", iteration + 1)
            raise

        choice = response.choices[0]
        tool_names = [tc.function.name for tc in (choice.message.tool_calls or [])]
        logger.info(
            "LLM response: tool_calls=%s, content_preview=%s",
            tool_names,
            (choice.message.content or "")[:200],
        )
        if generation:
            generation.end(output={"tool_calls": tool_names, "content_preview": (choice.message.content or "")[:200]})

        if not choice.message.tool_calls:
            # Final answer — no more tool calls
            if on_status:
                await on_status("\U0001f4ac Формулирую ответ...")
            elapsed = int((time.monotonic() - start) * 1000)
            answer = _strip_sources(choice.message.content or "")
            logger.info("Agent finished in %dms, %d tool calls, %d sources", elapsed, len(tools_used), len(sources))
            if trace:
                trace.update(output={"answer_preview": answer[:300], "latency_ms": elapsed, "sources": list(sources.values())})
                lf_flush()
            return AgentResult(
                answer=answer,
                tools_used=tools_used,
                sources=list(sources.values()),
                latency_ms=elapsed,
            )

        # Process tool calls — construct dict explicitly to avoid sending
        # unexpected fields back to the API (e.g. audio, function_call).
        assistant_msg: dict[str, Any] = {"role": "assistant", "content": choice.message.content}
        if choice.message.tool_calls:
            assistant_msg["tool_calls"] = [tc.model_dump() for tc in choice.message.tool_calls]
        messages.append(assistant_msg)

        for tool_call in choice.message.tool_calls:
            fn_name = tool_call.function.name
            try:
                fn_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                fn_args = {}

            if on_status:
                if fn_name == "search_corpus":
                    await on_status("\U0001f50d Ищу в монографиях...")
                elif fn_name == "get_passage":
                    await on_status("\U0001f4ac Читаю фрагмент...")

            logger.info("Calling tool %s with args: %s", fn_name, fn_args)
            tool_span = trace.span(name=f"tool-{fn_name}", input=fn_args) if trace else None
            raw_result = None
            try:
                result_text, raw_result = await _execute_tool(fn_name, fn_args, ai_client=ai_client)
                logger.info("Tool %s returned %d chars, preview: %s", fn_name, len(result_text), result_text[:300])
                if tool_span:
                    tool_span.end(output={"chars": len(result_text)})
            except Exception as exc:
                logger.exception("Tool %s failed: %s", fn_name, exc)
                if tool_span:
                    tool_span.end(output={"error": str(exc)}, level="ERROR")
                result_text = json.dumps(
                    {"error": f"Tool {fn_name} failed, try a different query."},
                    ensure_ascii=False,
                )

            tools_used.append({"tool": fn_name, "args": fn_args, "iteration": iteration})

            # Track sources from raw search results (before JSON truncation)
            if fn_name == "search_corpus" and isinstance(raw_result, list):
                for item in raw_result:
                    if isinstance(item, dict) and item.get("doc_id") and item.get("doc_title"):
                        sources[item["doc_id"]] = item["doc_title"]

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_text,
                }
            )

    # Iterations exhausted — force a final answer
    logger.warning("Agent exhausted %d iterations, forcing final answer", settings.max_agent_iterations)
    messages.append(
        {"role": "system", "content": "Сформируй ответ на основе собранной информации."}
    )

    try:
        response = await ai_client.chat_completion(messages, tools=None, max_tokens=4000)
    except Exception:
        logger.exception("LLM call failed on forced final answer")
        raise

    if on_status:
        await on_status("\U0001f4ac Формулирую ответ...")

    elapsed = int((time.monotonic() - start) * 1000)
    answer = _strip_sources(response.choices[0].message.content or "")
    if trace:
        trace.update(output={"answer_preview": answer[:300], "latency_ms": elapsed, "sources": list(sources.values())})
        lf_flush()
    return AgentResult(
        answer=answer,
        tools_used=tools_used,
        sources=list(sources.values()),
        latency_ms=elapsed,
    )

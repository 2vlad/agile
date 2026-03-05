import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from config.settings import get_settings
from rag.prompts import get_system_prompt
from rag.tools import TOOL_SCHEMAS, get_passage, search_corpus
from yandex.ai_studio import YandexAIStudio

logger = logging.getLogger(__name__)

TOOL_RESULT_MAX_CHARS = 12_000


@dataclass
class AgentResult:
    answer: str
    tools_used: list[dict] = field(default_factory=list)
    latency_ms: int = 0


async def _execute_tool(
    name: str,
    arguments: dict[str, Any],
    ai_client: YandexAIStudio | None = None,
) -> str:
    """Dispatch a tool call and return its JSON-encoded result."""
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
    return text


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

    if on_status:
        await on_status("🔍 Ищу в монографиях...")

    system_prompt = get_system_prompt(doc_titles or [], max_iterations=settings.max_agent_iterations)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": query},
    ]

    tools_used: list[dict] = []
    got_passage = False

    for iteration in range(settings.max_agent_iterations):
        logger.debug("Agent iteration %d/%d", iteration + 1, settings.max_agent_iterations)

        try:
            response = await ai_client.chat_completion(messages, tools=TOOL_SCHEMAS)
        except Exception:
            logger.exception("LLM call failed on iteration %d", iteration + 1)
            raise

        choice = response.choices[0]

        if not choice.message.tool_calls:
            # Final answer — no more tool calls
            if on_status:
                await on_status("✍️ Формирую ответ...")
            elapsed = int((time.monotonic() - start) * 1000)
            return AgentResult(
                answer=choice.message.content or "",
                tools_used=tools_used,
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

            if fn_name == "get_passage" and not got_passage:
                got_passage = True
                if on_status:
                    await on_status("📚 Расширяю контекст...")

            try:
                result_text = await _execute_tool(fn_name, fn_args, ai_client=ai_client)
            except Exception as exc:
                logger.warning("Tool %s failed: %s", fn_name, exc)
                result_text = json.dumps(
                    {"error": f"Tool {fn_name} failed, try a different query."},
                    ensure_ascii=False,
                )

            tools_used.append({"tool": fn_name, "args": fn_args, "iteration": iteration})

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
        await on_status("✍️ Формирую ответ...")

    elapsed = int((time.monotonic() - start) * 1000)
    return AgentResult(
        answer=response.choices[0].message.content or "",
        tools_used=tools_used,
        latency_ms=elapsed,
    )

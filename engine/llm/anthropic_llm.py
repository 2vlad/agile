"""Anthropic LLM provider — wraps responses into OpenAI-compatible format."""

import json
import logging
from dataclasses import dataclass
from typing import Any

from engine.llm.base import LLMClient

logger = logging.getLogger(__name__)


@dataclass
class _FunctionCall:
    name: str
    arguments: str


@dataclass
class _ToolCall:
    id: str
    type: str
    function: _FunctionCall

    def model_dump(self) -> dict:
        return {"id": self.id, "type": self.type, "function": {"name": self.function.name, "arguments": self.function.arguments}}


@dataclass
class _Message:
    role: str
    content: str | None
    tool_calls: list[_ToolCall] | None


@dataclass
class _Choice:
    message: _Message


@dataclass
class _Response:
    choices: list[_Choice]


def _convert_messages(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """Split OpenAI messages into Anthropic system + messages."""
    system = ""
    converted = []
    for msg in messages:
        if msg["role"] == "system":
            system += msg["content"] + "\n"
        elif msg["role"] == "tool":
            converted.append({
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": msg.get("tool_call_id", ""), "content": msg["content"]}],
            })
        else:
            converted.append({"role": msg["role"], "content": msg.get("content") or ""})
    return system.strip(), converted


class AnthropicLLM(LLMClient):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514") -> None:
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            raise ImportError("pip install anthropic")
        self._model = model
        self._client = AsyncAnthropic(api_key=api_key)

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4000,
    ) -> Any:
        system, converted_messages = _convert_messages(messages)

        kwargs: dict[str, Any] = dict(
            model=self._model,
            messages=converted_messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = [
                {"name": t["function"]["name"], "description": t["function"]["description"], "input_schema": t["function"]["parameters"]}
                for t in tools
            ]

        response = await self._client.messages.create(**kwargs)

        # Convert to OpenAI-compatible format
        content = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append(_ToolCall(
                    id=block.id,
                    type="function",
                    function=_FunctionCall(name=block.name, arguments=json.dumps(block.input)),
                ))

        return _Response(choices=[_Choice(message=_Message(
            role="assistant",
            content=content or None,
            tool_calls=tool_calls or None,
        ))])

    async def close(self) -> None:
        pass

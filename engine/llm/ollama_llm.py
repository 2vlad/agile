"""Ollama LLM — OpenAI-compatible local endpoint."""

from typing import Any

from openai import AsyncOpenAI

from engine.llm.base import LLMClient


class OllamaLLM(LLMClient):
    def __init__(self, model: str = "llama3", base_url: str = "http://localhost:11434/v1") -> None:
        self._model = model
        self._client = AsyncOpenAI(api_key="ollama", base_url=base_url)

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4000,
    ) -> Any:
        kwargs: dict[str, Any] = dict(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        return await self._client.chat.completions.create(**kwargs)

    async def close(self) -> None:
        await self._client.close()

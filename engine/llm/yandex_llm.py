"""Yandex AI Studio LLM — OpenAI-compatible endpoint."""

from typing import Any

from engine.llm.base import LLMClient


class YandexLLM(LLMClient):
    def __init__(self, api_key: str, folder_id: str, model: str = "yandexgpt", base_url: str = "https://ai.api.cloud.yandex.net/v1") -> None:
        try:
            from langfuse.openai import AsyncOpenAI
        except ImportError:
            from openai import AsyncOpenAI

        # Build full model URI if short name given
        if not model.startswith("gpt://"):
            if "/" not in model:
                model = f"{model}/latest"
            model = f"gpt://{folder_id}/{model}"

        self._model = model
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers={
                "OpenAI-Project": folder_id,
                "Authorization": f"Api-Key {api_key}",
            },
        )

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

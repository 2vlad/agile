import asyncio
import logging
from typing import Any

import httpx

try:
    from langfuse.openai import AsyncOpenAI
except ImportError:
    from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 256  # Yandex text-search-doc/query models output 256 dimensions


class YandexAIStudio:
    """Client for Yandex AI Studio.

    Uses openai SDK for chat completions (OpenAI-compatible endpoint).
    Uses httpx for embeddings (separate REST API, NOT OpenAI-compatible).
    """

    def __init__(
        self,
        api_key: str,
        folder_id: str,
        llm_model: str,
        embed_doc_model: str,
        embed_query_model: str,
        llm_base_url: str = "https://ai.api.cloud.yandex.net/v1",
        embeddings_url: str = "https://llm.api.cloud.yandex.net/foundationModels/v1/textEmbedding",
    ) -> None:
        self._llm_model = llm_model
        self._embed_doc_model = embed_doc_model
        self._embed_query_model = embed_query_model
        self._embeddings_url = embeddings_url

        # OpenAI-compatible LLM client
        self._llm = AsyncOpenAI(
            api_key=api_key,
            base_url=llm_base_url,
            default_headers={
                "OpenAI-Project": folder_id,
                "Authorization": f"Api-Key {api_key}",
            },
        )

        # httpx client for Yandex Embeddings REST API
        self._http = httpx.AsyncClient(
            headers={
                "Authorization": f"Api-Key {api_key}",
                "x-folder-id": folder_id,
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

    async def get_embedding(self, text: str, *, for_query: bool = False) -> list[float]:
        """Get embedding vector. Use for_query=True for user queries, False for document chunks."""
        model_uri = self._embed_query_model if for_query else self._embed_doc_model
        resp = await self._http.post(
            self._embeddings_url,
            json={"modelUri": model_uri, "text": text},
        )
        if resp.status_code != 200:
            logger.error("Embedding API error %s: %s", resp.status_code, resp.text)
        resp.raise_for_status()
        embedding = resp.json()["embedding"]
        assert len(embedding) == EMBEDDING_DIM, (
            f"Expected {EMBEDDING_DIM}-dim embedding, got {len(embedding)}"
        )
        return embedding

    async def get_doc_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings for document chunks (sequential to respect rate limits)."""
        results: list[list[float]] = []
        for i, text in enumerate(texts):
            embedding = await self.get_embedding(text, for_query=False)
            results.append(embedding)
            if (i + 1) % 10 == 0:
                logger.debug(f"Embedded {i + 1}/{len(texts)} chunks")
                await asyncio.sleep(1.0)  # respect 10 req/s rate limit
        return results

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 3000,
    ) -> Any:
        """Call Yandex LLM via OpenAI-compatible chat completions API."""
        kwargs: dict[str, Any] = dict(
            model=self._llm_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        return await self._llm.chat.completions.create(**kwargs)

    async def close(self) -> None:
        await self._http.aclose()
        await self._llm.close()

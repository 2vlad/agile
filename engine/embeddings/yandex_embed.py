"""Yandex AI Studio embeddings — REST API (not OpenAI-compatible)."""

import asyncio
import logging

import httpx

from engine.embeddings.base import EmbeddingClient

logger = logging.getLogger(__name__)


class YandexEmbedding(EmbeddingClient):
    def __init__(
        self,
        api_key: str,
        folder_id: str,
        doc_model: str = "",
        query_model: str = "",
        dim: int = 256,
        url: str = "https://llm.api.cloud.yandex.net/foundationModels/v1/textEmbedding",
    ) -> None:
        self.embedding_dim = dim
        self._doc_model = doc_model or f"emb://{folder_id}/text-search-doc/latest"
        self._query_model = query_model or f"emb://{folder_id}/text-search-query/latest"
        self._url = url
        self._http = httpx.AsyncClient(
            headers={"Authorization": f"Api-Key {api_key}", "x-folder-id": folder_id},
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

    async def get_embedding(self, text: str, *, for_query: bool = False) -> list[float]:
        model_uri = self._query_model if for_query else self._doc_model
        resp = await self._http.post(self._url, json={"modelUri": model_uri, "text": text})
        resp.raise_for_status()
        return resp.json()["embedding"]

    async def get_doc_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        for i, text in enumerate(texts):
            embedding = await self.get_embedding(text, for_query=False)
            results.append(embedding)
            if (i + 1) % 10 == 0:
                logger.debug("Embedded %d/%d chunks", i + 1, len(texts))
                await asyncio.sleep(1.0)  # Yandex rate limit: 10 req/s
        return results

    async def close(self) -> None:
        await self._http.aclose()

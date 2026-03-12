"""Ollama embeddings — OpenAI-compatible local endpoint."""

import asyncio
import logging

from openai import AsyncOpenAI

from engine.embeddings.base import EmbeddingClient

logger = logging.getLogger(__name__)


class OllamaEmbedding(EmbeddingClient):
    def __init__(self, model: str = "nomic-embed-text", dim: int = 768, base_url: str = "http://localhost:11434/v1") -> None:
        self.embedding_dim = dim
        self._model = model
        self._client = AsyncOpenAI(api_key="ollama", base_url=base_url)

    async def get_embedding(self, text: str, *, for_query: bool = False) -> list[float]:
        response = await self._client.embeddings.create(model=self._model, input=text)
        return response.data[0].embedding[:self.embedding_dim]

    async def get_doc_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        for i, text in enumerate(texts):
            embedding = await self.get_embedding(text, for_query=False)
            results.append(embedding)
            if (i + 1) % 10 == 0:
                logger.debug("Embedded %d/%d chunks", i + 1, len(texts))
                await asyncio.sleep(0.1)
        return results

    async def close(self) -> None:
        await self._client.close()

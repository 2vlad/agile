import asyncio
import logging

from openai import AsyncOpenAI

from engine.embeddings.base import EmbeddingClient

logger = logging.getLogger(__name__)


class OpenAIEmbedding(EmbeddingClient):
    def __init__(self, api_key: str, model: str = "text-embedding-3-small", dim: int = 1536, base_url: str | None = None) -> None:
        self.embedding_dim = dim
        self._model = model
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def get_embedding(self, text: str, *, for_query: bool = False) -> list[float]:
        response = await self._client.embeddings.create(model=self._model, input=text)
        return response.data[0].embedding[:self.embedding_dim]

    async def get_doc_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        # OpenAI supports batch embeddings natively
        batch_size = 100
        results: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = await self._client.embeddings.create(model=self._model, input=batch)
            for item in response.data:
                results.append(item.embedding[:self.embedding_dim])
            if i + batch_size < len(texts):
                await asyncio.sleep(0.1)  # light rate limiting
            logger.debug("Embedded %d/%d chunks", len(results), len(texts))
        return results

    async def close(self) -> None:
        await self._client.close()

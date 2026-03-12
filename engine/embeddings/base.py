from abc import ABC, abstractmethod


class EmbeddingClient(ABC):
    """Abstract base class for embedding providers."""

    embedding_dim: int

    @abstractmethod
    async def get_embedding(self, text: str, *, for_query: bool = False) -> list[float]:
        ...

    @abstractmethod
    async def get_doc_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...

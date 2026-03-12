from engine.embeddings.base import EmbeddingClient


def create_embedding_client(
    provider: str,
    api_key: str = "",
    model: str = "",
    dim: int = 1536,
    base_url: str = "",
    folder_id: str = "",
) -> EmbeddingClient:
    """Factory to create an embedding client based on provider name."""
    if provider == "openai":
        from engine.embeddings.openai_embed import OpenAIEmbedding
        return OpenAIEmbedding(api_key=api_key, model=model or "text-embedding-3-small", dim=dim, base_url=base_url or None)

    if provider == "yandex":
        from engine.embeddings.yandex_embed import YandexEmbedding
        return YandexEmbedding(api_key=api_key, folder_id=folder_id, dim=dim, url=base_url or "https://llm.api.cloud.yandex.net/foundationModels/v1/textEmbedding")

    if provider == "ollama":
        from engine.embeddings.ollama_embed import OllamaEmbedding
        return OllamaEmbedding(model=model or "nomic-embed-text", dim=dim, base_url=base_url or "http://localhost:11434/v1")

    raise ValueError(f"Unknown embedding provider: {provider}. Supported: openai, yandex, ollama")

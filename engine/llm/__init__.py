from engine.llm.base import LLMClient


def create_llm_client(
    provider: str,
    api_key: str = "",
    model: str = "",
    base_url: str = "",
    folder_id: str = "",
) -> LLMClient:
    """Factory to create an LLM client based on provider name."""
    if provider == "openai":
        from engine.llm.openai_llm import OpenAILLM
        return OpenAILLM(api_key=api_key, model=model or "gpt-4o-mini", base_url=base_url or None)

    if provider == "anthropic":
        from engine.llm.anthropic_llm import AnthropicLLM
        return AnthropicLLM(api_key=api_key, model=model or "claude-sonnet-4-20250514")

    if provider == "yandex":
        from engine.llm.yandex_llm import YandexLLM
        return YandexLLM(api_key=api_key, folder_id=folder_id, model=model or "yandexgpt", base_url=base_url or "https://ai.api.cloud.yandex.net/v1")

    if provider == "ollama":
        from engine.llm.ollama_llm import OllamaLLM
        return OllamaLLM(model=model or "llama3", base_url=base_url or "http://localhost:11434/v1")

    raise ValueError(f"Unknown LLM provider: {provider}. Supported: openai, anthropic, yandex, ollama")

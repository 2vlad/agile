from abc import ABC, abstractmethod
from typing import Any


class LLMClient(ABC):
    """Abstract base class for LLM providers.

    All providers return OpenAI-compatible ChatCompletion objects
    so the pipeline doesn't need provider-specific parsing.
    """

    @abstractmethod
    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4000,
    ) -> Any:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...

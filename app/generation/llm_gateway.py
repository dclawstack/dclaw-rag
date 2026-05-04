from abc import ABC, abstractmethod

from app.core.config import settings
from app.core.exceptions import GenerationError


class LLMGateway(ABC):
    @abstractmethod
    async def complete(self, messages: list[dict], temperature: float = 0.2) -> str:
        ...


class OpenAIGateway(LLMGateway):
    def __init__(self) -> None:
        import openai

        self.client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.llm_model

    async def complete(self, messages: list[dict], temperature: float = 0.2) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            raise GenerationError(f"OpenAI completion failed: {exc}") from exc


class AnthropicGateway(LLMGateway):
    def __init__(self) -> None:
        import anthropic

        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.llm_model

    async def complete(self, messages: list[dict], temperature: float = 0.2) -> str:
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                temperature=temperature,
                messages=messages,
            )
            return response.content[0].text if response.content else ""
        except Exception as exc:
            raise GenerationError(f"Anthropic completion failed: {exc}") from exc


def get_llm_gateway() -> LLMGateway:
    provider = settings.llm_provider.lower()
    if provider == "openai":
        return OpenAIGateway()
    if provider == "anthropic":
        return AnthropicGateway()
    raise GenerationError(f"Unsupported LLM provider: {provider}")

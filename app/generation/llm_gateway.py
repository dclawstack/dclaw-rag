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


class OllamaGateway(LLMGateway):
    def __init__(self) -> None:
        self.url = settings.ollama_url.rstrip("/")
        self.model = settings.ollama_model

    async def complete(self, messages: list[dict], temperature: float = 0.2) -> str:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                        "options": {"temperature": temperature},
                    },
                )
                response.raise_for_status()
                return response.json().get("message", {}).get("content", "")
        except Exception as exc:
            raise GenerationError(f"Ollama completion failed: {exc}") from exc


class FallbackGateway(LLMGateway):
    """Try the primary (cloud) gateway; on failure, fall back to a local one."""

    def __init__(self, primary: LLMGateway, fallback: LLMGateway) -> None:
        self.primary = primary
        self.fallback = fallback

    async def complete(self, messages: list[dict], temperature: float = 0.2) -> str:
        try:
            return await self.primary.complete(messages, temperature)
        except GenerationError:
            return await self.fallback.complete(messages, temperature)


def _build_gateway(provider: str) -> LLMGateway:
    if provider == "openai":
        return OpenAIGateway()
    if provider == "anthropic":
        return AnthropicGateway()
    if provider == "ollama":
        return OllamaGateway()
    raise GenerationError(f"Unsupported LLM provider: {provider}")


def get_llm_gateway() -> LLMGateway:
    provider = settings.llm_provider.lower()
    primary = _build_gateway(provider)
    if provider != "ollama" and settings.llm_fallback_to_ollama:
        return FallbackGateway(primary, OllamaGateway())
    return primary

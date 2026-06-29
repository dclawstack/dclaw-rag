from abc import ABC, abstractmethod

import structlog

from app.core.config import settings
from app.core.exceptions import GenerationError

logger = structlog.get_logger(__name__)


class LLMGateway(ABC):
    @abstractmethod
    async def complete(self, messages: list[dict], temperature: float = 0.2) -> str:
        ...


class OpenAIGateway(LLMGateway):
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        import openai

        # base_url defaults to OpenAI; pass an OpenAI-compatible URL (e.g. OpenRouter).
        self.client = openai.AsyncOpenAI(
            api_key=api_key or settings.openai_api_key,
            base_url=base_url,
        )
        self.model = model or settings.llm_model

    async def complete(self, messages: list[dict], temperature: float = 0.2) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]  # plain dicts; OpenAI wants typed message params
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
        # Anthropic takes the system prompt as a top-level `system` arg, not a
        # message with role "system" (which it rejects). Split it out.
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        chat = [m for m in messages if m["role"] != "system"]
        kwargs: dict = {
            "model": self.model,
            "max_tokens": 2048,
            "temperature": temperature,
            "messages": chat,
        }
        if system:
            kwargs["system"] = system
        try:
            response = await self.client.messages.create(**kwargs)
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
        except GenerationError as primary_exc:
            # Warn loudly: otherwise a misconfig (e.g. a bad model id) silently
            # masquerades as success while answers quietly come from the fallback.
            logger.warning(
                "llm_primary_failed_using_fallback",
                error=str(primary_exc),
                fallback=type(self.fallback).__name__,
            )
            try:
                return await self.fallback.complete(messages, temperature)
            except GenerationError as fallback_exc:
                raise GenerationError(
                    f"primary failed: {primary_exc}; fallback failed: {fallback_exc}"
                ) from fallback_exc


def _build_gateway(provider: str) -> LLMGateway:
    if provider == "openai":
        return OpenAIGateway()
    if provider == "openrouter":
        return OpenAIGateway(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            model=settings.openrouter_model,
        )
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

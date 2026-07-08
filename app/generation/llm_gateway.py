import threading
from abc import ABC, abstractmethod
from typing import Any

import structlog

from app.core import metering
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
            usage = getattr(response, "usage", None)
            if usage:
                metering.record(self.model, usage.prompt_tokens, usage.completion_tokens)
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
            usage = getattr(response, "usage", None)
            if usage:
                metering.record(self.model, usage.input_tokens, usage.output_tokens)
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
                data = response.json()
                metering.record(
                    self.model,
                    data.get("prompt_eval_count", 0),
                    data.get("eval_count", 0),
                )
                return data.get("message", {}).get("content", "")
        except Exception as exc:
            raise GenerationError(f"Ollama completion failed: {exc}") from exc


class LlamaCppGateway(LLMGateway):
    """In-process llama.cpp GGUF runner — the bundled, fully-local answer engine.

    No second daemon and no network at inference time (contrast OllamaGateway,
    which talks to a separate `ollama serve`). The model weights are heavy, so
    the underlying `Llama` object is a process-wide singleton loaded lazily on
    the first completion; `create_chat_completion` is blocking, so we run it off
    the event loop. The GGUF is loaded from `local_llm_model_path` if set,
    otherwise downloaded once from Hugging Face and cached under data_dir/models.
    """

    _llama: Any | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self.max_tokens = settings.local_llm_max_tokens
        # Label for metering — the file/repo the answer actually came from.
        self.model = settings.local_llm_model_path or settings.local_llm_model_file

    @classmethod
    def _get_llama(cls) -> Any:
        if cls._llama is None:
            with cls._lock:
                if cls._llama is None:
                    cls._llama = cls._load()
        return cls._llama

    @staticmethod
    def _load() -> Any:
        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise GenerationError(
                "local LLM provider requires 'llama-cpp-python' — install the "
                "'local-llm' extra (pip install -e '.[local-llm]')"
            ) from exc

        common: dict[str, Any] = {
            "n_ctx": settings.local_llm_n_ctx,
            "verbose": False,
        }
        if settings.local_llm_n_threads is not None:
            common["n_threads"] = settings.local_llm_n_threads
        try:
            if settings.local_llm_model_path:
                logger.info("local_llm_loading", path=settings.local_llm_model_path)
                return Llama(model_path=settings.local_llm_model_path, **common)
            settings.local_llm_dir.mkdir(parents=True, exist_ok=True)
            logger.info(
                "local_llm_loading",
                repo=settings.local_llm_model_repo,
                file=settings.local_llm_model_file,
            )
            return Llama.from_pretrained(
                repo_id=settings.local_llm_model_repo,
                filename=settings.local_llm_model_file,
                cache_dir=str(settings.local_llm_dir),
                **common,
            )
        except Exception as exc:  # download / load / OOM
            raise GenerationError(f"local LLM model failed to load: {exc}") from exc

    async def complete(self, messages: list[dict], temperature: float = 0.2) -> str:
        import anyio

        llama = self._get_llama()

        def _run() -> str:
            response = llama.create_chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=self.max_tokens,
            )
            usage = response.get("usage")
            if usage:
                metering.record(
                    self.model,
                    usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0),
                )
            choices = response.get("choices") or []
            if not choices:
                return ""
            return choices[0].get("message", {}).get("content", "") or ""

        try:
            return await anyio.to_thread.run_sync(_run)
        except GenerationError:
            raise
        except Exception as exc:
            raise GenerationError(f"local LLM completion failed: {exc}") from exc


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
    if provider == "local":
        return LlamaCppGateway()
    raise GenerationError(f"Unsupported LLM provider: {provider}")


# Providers that are already fully local: they need no key and it makes no sense
# to wrap them in an Ollama fallback.
_LOCAL_PROVIDERS = {"ollama", "local"}


def get_llm_gateway() -> LLMGateway:
    provider = settings.llm_provider.lower()
    try:
        primary = _build_gateway(provider)
    except Exception as exc:
        # A missing key can fail at client CONSTRUCTION (e.g. openai raises
        # before any completion is attempted) — honor the Ollama fallback
        # instead of turning every query into a 500.
        if provider not in _LOCAL_PROVIDERS and settings.llm_fallback_to_ollama:
            logger.warning(
                "llm_primary_unavailable_using_fallback", provider=provider, error=str(exc)
            )
            return OllamaGateway()
        raise
    if provider not in _LOCAL_PROVIDERS and settings.llm_fallback_to_ollama:
        return FallbackGateway(primary, OllamaGateway())
    return primary

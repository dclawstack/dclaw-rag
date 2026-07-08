import pytest

from app.core.exceptions import GenerationError
from app.generation import llm_gateway
from app.generation.llm_gateway import (
    AnthropicGateway,
    FallbackGateway,
    LlamaCppGateway,
    LLMGateway,
    OllamaGateway,
    get_llm_gateway,
)


class _OkGateway(LLMGateway):
    def __init__(self, text="ok"):
        self.text = text
        self.called = False

    async def complete(self, messages, temperature=0.2):
        self.called = True
        return self.text


class _FailingGateway(LLMGateway):
    def __init__(self):
        self.called = False

    async def complete(self, messages, temperature=0.2):
        self.called = True
        raise GenerationError("primary down")


async def test_fallback_uses_primary_when_it_succeeds():
    primary = _OkGateway("from primary")
    fallback = _OkGateway("from fallback")
    gateway = FallbackGateway(primary, fallback)

    result = await gateway.complete([{"role": "user", "content": "hi"}])

    assert result == "from primary"
    assert primary.called
    assert not fallback.called


async def test_fallback_switches_to_fallback_on_primary_failure():
    primary = _FailingGateway()
    fallback = _OkGateway("from fallback")
    gateway = FallbackGateway(primary, fallback)

    result = await gateway.complete([{"role": "user", "content": "hi"}])

    assert result == "from fallback"
    assert primary.called


class _FailingFallback(LLMGateway):
    async def complete(self, messages, temperature=0.2):
        raise GenerationError("fallback down")


async def test_fallback_raises_combined_error_when_both_fail():
    gateway = FallbackGateway(_FailingGateway(), _FailingFallback())

    with pytest.raises(GenerationError) as exc_info:
        await gateway.complete([{"role": "user", "content": "hi"}])

    message = str(exc_info.value)
    assert "primary down" in message  # the real cause is not masked
    assert "fallback down" in message


class _RecordingMessages:
    def __init__(self):
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        block = type("Block", (), {"type": "text", "text": "answer"})()
        return type("Resp", (), {"content": [block]})()


class _RecordingClient:
    def __init__(self):
        self.messages = _RecordingMessages()


async def test_anthropic_gateway_splits_system_into_top_level_arg():
    # bypass __init__ so we don't construct a real anthropic client
    gateway = AnthropicGateway.__new__(AnthropicGateway)
    gateway.client = _RecordingClient()
    gateway.model = "claude-sonnet-4-6"

    out = await gateway.complete(
        [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "hi"},
        ]
    )

    assert out == "answer"
    kwargs = gateway.client.messages.kwargs
    assert kwargs["system"] == "You are helpful."  # system hoisted out
    assert kwargs["messages"] == [{"role": "user", "content": "hi"}]  # no system role
    assert all(m["role"] != "system" for m in kwargs["messages"])


def test_get_llm_gateway_wraps_cloud_provider_with_ollama_fallback(monkeypatch):
    # Stub the cloud gateway so the test doesn't require the provider SDK.
    monkeypatch.setattr(llm_gateway.settings, "llm_provider", "anthropic")
    monkeypatch.setattr(llm_gateway, "AnthropicGateway", _OkGateway)
    monkeypatch.setattr(llm_gateway.settings, "llm_fallback_to_ollama", True)

    gateway = get_llm_gateway()

    assert isinstance(gateway, FallbackGateway)
    assert isinstance(gateway.fallback, OllamaGateway)


def test_get_llm_gateway_ollama_provider_is_not_wrapped(monkeypatch):
    monkeypatch.setattr(llm_gateway.settings, "llm_provider", "ollama")

    gateway = get_llm_gateway()

    assert isinstance(gateway, OllamaGateway)


def test_get_llm_gateway_openrouter_builds_openai_client_with_base_url(monkeypatch):
    captured = {}

    class _StubOpenAI(LLMGateway):
        def __init__(self, api_key=None, base_url=None, model=None):
            captured.update(api_key=api_key, base_url=base_url, model=model)

        async def complete(self, messages, temperature=0.2):
            return ""

    monkeypatch.setattr(llm_gateway.settings, "llm_provider", "openrouter")
    monkeypatch.setattr(llm_gateway.settings, "openrouter_api_key", "sk-or-test")
    monkeypatch.setattr(llm_gateway.settings, "openrouter_model", "openai/gpt-4o-mini")
    monkeypatch.setattr(llm_gateway.settings, "llm_fallback_to_ollama", False)
    monkeypatch.setattr(llm_gateway, "OpenAIGateway", _StubOpenAI)

    gateway = get_llm_gateway()

    assert isinstance(gateway, _StubOpenAI)
    assert captured["api_key"] == "sk-or-test"
    assert captured["base_url"] == llm_gateway.settings.openrouter_base_url
    assert captured["model"] == "openai/gpt-4o-mini"


def test_get_llm_gateway_fallback_disabled(monkeypatch):
    monkeypatch.setattr(llm_gateway.settings, "llm_provider", "anthropic")
    monkeypatch.setattr(llm_gateway, "AnthropicGateway", _OkGateway)
    monkeypatch.setattr(llm_gateway.settings, "llm_fallback_to_ollama", False)

    gateway = get_llm_gateway()

    assert not isinstance(gateway, FallbackGateway)
    assert isinstance(gateway, _OkGateway)


def test_missing_key_falls_back_to_ollama_at_construction(monkeypatch):
    from app.core.config import settings
    from app.generation.llm_gateway import OllamaGateway, get_llm_gateway

    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(settings, "llm_fallback_to_ollama", True)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert isinstance(get_llm_gateway(), OllamaGateway)


def test_get_llm_gateway_local_provider_is_not_wrapped(monkeypatch):
    # A "local" provider is already fully local: no key, no Ollama fallback wrap.
    monkeypatch.setattr(llm_gateway.settings, "llm_provider", "local")
    monkeypatch.setattr(llm_gateway.settings, "llm_fallback_to_ollama", True)

    gateway = get_llm_gateway()

    assert isinstance(gateway, LlamaCppGateway)


class _FakeLlama:
    def __init__(self):
        self.calls = []

    def create_chat_completion(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "choices": [{"message": {"role": "assistant", "content": "local answer"}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7},
        }


async def test_llamacpp_gateway_completes_and_meters(monkeypatch):
    fake = _FakeLlama()
    monkeypatch.setattr(LlamaCppGateway, "_llama", fake)
    recorded = []
    monkeypatch.setattr(
        llm_gateway.metering, "record", lambda *a, **k: recorded.append((a, k))
    )

    gateway = LlamaCppGateway()
    out = await gateway.complete(
        [{"role": "user", "content": "hi"}], temperature=0.4
    )

    assert out == "local answer"
    assert fake.calls[0]["temperature"] == 0.4
    assert fake.calls[0]["max_tokens"] == gateway.max_tokens
    assert recorded and recorded[0][0][1:] == (11, 7)  # prompt/completion tokens metered


def test_llamacpp_load_without_package_raises_helpful_error(monkeypatch):
    # Force the llama_cpp import to fail and assert the message points at the extra.
    monkeypatch.setattr(LlamaCppGateway, "_llama", None)
    import builtins

    real_import = builtins.__import__

    def _no_llama(name, *args, **kwargs):
        if name == "llama_cpp":
            raise ImportError("No module named 'llama_cpp'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_llama)

    with pytest.raises(GenerationError) as exc_info:
        LlamaCppGateway._load()

    assert "local-llm" in str(exc_info.value)


def test_missing_key_without_fallback_raises(monkeypatch):
    import pytest as _pytest

    from app.core.config import settings
    from app.generation.llm_gateway import get_llm_gateway

    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(settings, "llm_fallback_to_ollama", False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    import openai

    with _pytest.raises(openai.OpenAIError):
        get_llm_gateway()

from app.core.exceptions import GenerationError
from app.generation import llm_gateway
from app.generation.llm_gateway import (
    FallbackGateway,
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
    assert fallback.called


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


def test_get_llm_gateway_fallback_disabled(monkeypatch):
    monkeypatch.setattr(llm_gateway.settings, "llm_provider", "anthropic")
    monkeypatch.setattr(llm_gateway, "AnthropicGateway", _OkGateway)
    monkeypatch.setattr(llm_gateway.settings, "llm_fallback_to_ollama", False)

    gateway = get_llm_gateway()

    assert not isinstance(gateway, FallbackGateway)
    assert isinstance(gateway, _OkGateway)

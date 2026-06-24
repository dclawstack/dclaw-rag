import pytest

from app.core.exceptions import GenerationError
from app.generation import llm_gateway
from app.generation.llm_gateway import (
    AnthropicGateway,
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


def test_get_llm_gateway_fallback_disabled(monkeypatch):
    monkeypatch.setattr(llm_gateway.settings, "llm_provider", "anthropic")
    monkeypatch.setattr(llm_gateway, "AnthropicGateway", _OkGateway)
    monkeypatch.setattr(llm_gateway.settings, "llm_fallback_to_ollama", False)

    gateway = get_llm_gateway()

    assert not isinstance(gateway, FallbackGateway)
    assert isinstance(gateway, _OkGateway)

import asyncio
import json

import httpx
import pytest

from app.core.config import Settings
from app.services.errors import InvalidModelOutput, LLMConfigurationError, LLMProviderError
from app.services.llm_service import LLMClient, parse_json_response
from app.services.providers import GeminiProvider, OpenAICompatibleProvider, build_provider
from tests.helpers import FakeProvider


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    async def instant(_seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", instant)


def mock(handler):
    return httpx.MockTransport(handler)


def gemini(handler, **kw):
    return GeminiProvider("gemini", "gem-model", "secret-key", transport=mock(handler), **kw)


def openai_style(handler, key="k", **kw):
    return OpenAICompatibleProvider(
        "groq", "m", key, base_url="https://example.test/v1", transport=mock(handler), **kw
    )


def test_parse_json():
    assert parse_json_response('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_response('Sure! Here it is: {"a": 2} hope that helps') == {"a": 2}
    assert parse_json_response('Result: [{"a": 3}]') == [{"a": 3}]
    with pytest.raises(InvalidModelOutput):
        parse_json_response("no json at all")


def test_gemini_request_shape_and_reply():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("x-goog-api-key")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}]})

    assert run(gemini(handler).generate("hi")) == '{"ok": true}'
    assert seen["key"] == "secret-key"
    assert "secret-key" not in seen["url"]
    assert seen["url"].endswith("/models/gem-model:generateContent")
    assert seen["body"]["generationConfig"]["responseMimeType"] == "application/json"


def test_gemini_empty_reply_is_an_error():
    provider = gemini(lambda request: httpx.Response(200, json={"candidates": []}))
    with pytest.raises(LLMProviderError, match="no text"):
        run(provider.generate("hi"))


def test_openai_style_request():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": ' {"x": 1} '}}]})

    assert run(openai_style(handler).generate("hi")) == '{"x": 1}'
    assert seen["auth"] == "Bearer k"
    assert seen["url"] == "https://example.test/v1/chat/completions"
    assert seen["body"]["response_format"] == {"type": "json_object"}


def test_no_auth_header_without_a_key():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    run(openai_style(handler, key="").generate("hi"))
    assert seen["auth"] is None


def test_json_mode_fallback():
    bodies = []

    def handler(request):
        body = json.loads(request.content)
        bodies.append(body)
        if "response_format" in body:
            return httpx.Response(400, json={"error": {"message": "json mode unsupported"}})
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    assert run(openai_style(handler).generate("hi")) == "{}"
    assert len(bodies) == 2 and "response_format" not in bodies[1]


def test_retries_server_errors_then_succeeds():
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(503, json={"error": "busy"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    assert run(openai_style(handler, max_retries=2).generate("hi")) == "{}"
    assert len(calls) == 3


def test_gives_up_after_the_retry_limit():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(429, json={"error": {"message": "rate limited"}})

    with pytest.raises(LLMProviderError, match="429"):
        run(openai_style(handler, max_retries=2).generate("hi"))
    assert len(calls) == 3


def test_does_not_retry_a_bad_key():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    with pytest.raises(LLMProviderError, match="bad key"):
        run(openai_style(handler, max_retries=2).generate("hi"))
    assert len(calls) == 1


def test_network_failure():
    def handler(request):
        raise httpx.ConnectError("down")

    with pytest.raises(LLMProviderError, match="Could not reach groq"):
        run(openai_style(handler, max_retries=1).generate("hi"))


def test_request_key_beats_env():
    settings = Settings(api_keys={"groq": "env-key"}, models={"groq": "env-model"})
    from_env = build_provider("groq", settings)
    assert (from_env.api_key, from_env.model) == ("env-key", "env-model")
    override = build_provider("groq", settings, api_key="student-key", model="other")
    assert (override.api_key, override.model) == ("student-key", "other")


def test_build_provider_errors():
    settings = Settings()
    with pytest.raises(LLMConfigurationError, match="No API key"):
        build_provider("openrouter", settings)
    with pytest.raises(LLMConfigurationError, match="No model"):
        build_provider("openrouter", settings, api_key="k")
    with pytest.raises(LLMConfigurationError, match="Unknown provider"):
        build_provider("nope", settings, api_key="k", model="m")


def test_ollama_needs_a_model_but_no_key():
    provider = build_provider("ollama", Settings(), model="llama3.2")
    assert provider.api_key == "" and provider.base_url == "http://localhost:11434/v1"


def test_client_retries_bad_output():
    provider = FakeProvider(["not json", '{"n": 1}'])
    result = run(LLMClient(provider).generate("p", lambda data: data["n"]))
    assert result == 1 and len(provider.prompts) == 2


def test_client_gives_up():
    provider = FakeProvider(["not json", '{"wrong": 1}'])
    with pytest.raises(InvalidModelOutput):
        run(LLMClient(provider).generate("p", lambda data: data["n"]))
    assert len(provider.prompts) == 2

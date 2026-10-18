import asyncio
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import PROVIDERS, Settings
from app.services.errors import LLMConfigurationError, LLMProviderError

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
TEMPERATURE = 0.2
SYSTEM_MESSAGE = "Follow the user's instructions exactly. Use only the study notes you are given."

OPENAI_STYLE_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
}


class Provider:
    def __init__(
        self,
        name: str,
        model: str,
        api_key: str = "",
        *,
        timeout: float = 45.0,
        max_retries: int = 2,
        base_url: str = "",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.name = name
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_url = base_url.rstrip("/")
        self.transport = transport

    async def generate(self, prompt: str) -> str:
        raise NotImplementedError

    async def _post(self, url: str, headers: dict[str, str], payload: dict[str, Any]) -> Any:
        for attempt in range(self.max_retries + 1):
            last_attempt = attempt == self.max_retries
            try:
                async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                    response = await client.post(url, headers=headers, json=payload)
                if response.status_code in RETRYABLE_STATUS and not last_attempt:
                    await asyncio.sleep(2**attempt)
                    continue
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                code = exc.response.status_code
                raise LLMProviderError(
                    f"{self.name} request failed ({code}): {_error_detail(exc.response)}",
                    status_code=code,
                ) from exc
            except httpx.HTTPError as exc:
                if last_attempt:
                    raise LLMProviderError(f"Could not reach {self.name} ({type(exc).__name__}).") from exc
                await asyncio.sleep(2**attempt)
            except ValueError as exc:
                raise LLMProviderError(f"{self.name} returned a response that is not JSON.") from exc
        raise LLMProviderError(f"{self.name} request failed.")


class GeminiProvider(Provider):
    async def generate(self, prompt: str) -> str:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{quote(self.model, safe='')}:generateContent"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": TEMPERATURE, "responseMimeType": "application/json"},
        }
        data = await self._post(url, {"x-goog-api-key": self.api_key}, payload)
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "\n".join(part.get("text", "") for part in parts).strip()
        except (KeyError, IndexError, TypeError, AttributeError):
            text = ""
        if not text:
            raise LLMProviderError("Gemini returned no text. The request may have been blocked.")
        return text


class OpenAICompatibleProvider(Provider):
    async def generate(self, prompt: str) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_MESSAGE},
                {"role": "user", "content": prompt},
            ],
            "temperature": TEMPERATURE,
            "response_format": {"type": "json_object"},
        }
        try:
            data = await self._post(url, headers, payload)
        except LLMProviderError as exc:
            if exc.status_code != 400:
                raise
            # Some models reject JSON mode. Try once more without it.
            payload.pop("response_format")
            data = await self._post(url, headers, payload)
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            text = ""
        if not isinstance(text, str) or not text.strip():
            raise LLMProviderError(f"{self.name} returned an empty response.")
        return text.strip()


def build_provider(
    name: str,
    settings: Settings,
    api_key: str | None = None,
    model: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> Provider:
    # a key or model sent with the request wins over the .env values
    if name not in PROVIDERS:
        raise LLMConfigurationError(f"Unknown provider '{name}'. Choose one of: {', '.join(PROVIDERS)}.")
    key = (api_key or settings.api_keys.get(name, "")).strip()
    model = (model or settings.models.get(name, "")).strip()
    if name != "ollama" and not key:
        raise LLMConfigurationError(
            f"No API key for {name}. Send it in the X-AI-Key header or set {name.upper()}_API_KEY."
        )
    if not model:
        raise LLMConfigurationError(
            f"No model chosen for {name}. Send it in the X-AI-Model header or set {name.upper()}_MODEL."
        )
    options = {
        "timeout": settings.llm_timeout_seconds,
        "max_retries": settings.llm_max_retries,
        "transport": transport,
    }
    if name == "gemini":
        return GeminiProvider(name, model, key, **options)
    base_url = settings.ollama_base_url if name == "ollama" else OPENAI_STYLE_URLS[name]
    return OpenAICompatibleProvider(name, model, key, base_url=base_url, **options)


def _error_detail(response: httpx.Response) -> str:
    try:
        data = response.json()
        error = data.get("error") if isinstance(data, dict) else None
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])[:300]
        if isinstance(error, str):
            return error[:300]
    except ValueError:
        pass
    return response.text[:300] or "No error detail provided."

import re

from fastapi import Header, HTTPException

from app.core.config import PROVIDERS, get_settings
from app.schemas.document import DocumentContext
from app.services.llm_service import LLMClient
from app.services.providers import build_provider

MODEL_NAME = re.compile(r"\w[\w.:\-]*(?:/\w[\w.:\-]*)*")


def get_llm_client(
    x_ai_provider: str | None = Header(default=None, description="gemini, groq, openrouter, openai or ollama"),
    x_ai_model: str | None = Header(default=None, description="Model ID for this request"),
    x_ai_key: str | None = Header(default=None, description="The student's own API key. Never stored or logged."),
) -> LLMClient:
    # headers win over the values in .env
    settings = get_settings()
    name = (x_ai_provider or settings.default_provider).strip().lower()
    if name not in PROVIDERS:
        raise HTTPException(422, f"Unknown provider '{name}'. Choose one of: {', '.join(PROVIDERS)}.")
    model = (x_ai_model or "").strip() or None
    if model and (len(model) > 100 or not MODEL_NAME.fullmatch(model)):
        raise HTTPException(422, "X-AI-Model contains characters a model ID should not have.")
    return LLMClient(build_provider(name, settings, api_key=x_ai_key, model=model))


def enforce_size_limit(document: DocumentContext) -> None:
    limit = get_settings().max_document_chars
    if sum(len(page.text) for page in document.pages) > limit:
        raise HTTPException(
            413,
            f"Document text is over the {limit:,}-character limit.",
        )

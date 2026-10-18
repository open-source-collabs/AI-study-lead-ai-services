import os
from dataclasses import dataclass, field
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

PROVIDERS = ("gemini", "groq", "openrouter", "openai", "ollama")
DEFAULT_MODELS = {"gemini": "gemini-3.8-flash", "groq": "openai/gpt-oss-120b"}


@dataclass(frozen=True)
class Settings:
    default_provider: str = "gemini"
    api_keys: dict[str, str] = field(default_factory=dict)
    models: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_MODELS))
    ollama_base_url: str = "http://localhost:11434/v1"
    max_upload_mb: int = 10
    max_document_chars: int = 180_000
    chunk_size: int = 1200
    chunk_overlap: int = 180
    llm_timeout_seconds: float = 45.0
    llm_max_retries: int = 2
    retrieval_threshold_chars: int = 30_000
    retrieval_top_k: int = 8
    cors_origins: tuple[str, ...] = ("http://localhost:3000", "http://localhost:5173")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


def _number(name: str, default, cast=int, minimum=None):
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = cast(raw)
    except ValueError:
        raise ValueError(f"{name} must be a number") from None
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    provider = os.getenv("AI_PROVIDER", "gemini").strip().lower()
    if provider not in PROVIDERS:
        raise ValueError(f"AI_PROVIDER must be one of: {', '.join(PROVIDERS)}")

    chunk_size = _number("CHUNK_SIZE", 1200, minimum=100)
    chunk_overlap = _number("CHUNK_OVERLAP", 180, minimum=0)
    if chunk_overlap >= chunk_size:
        raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")

    origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
    return Settings(
        default_provider=provider,
        api_keys={name: os.getenv(f"{name.upper()}_API_KEY", "").strip() for name in PROVIDERS},
        models={
            name: os.getenv(f"{name.upper()}_MODEL", "").strip() or DEFAULT_MODELS.get(name, "")
            for name in PROVIDERS
        },
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1").strip(),
        max_upload_mb=_number("MAX_UPLOAD_MB", 10, minimum=1),
        max_document_chars=_number("MAX_DOCUMENT_CHARS", 180_000, minimum=1000),
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        llm_timeout_seconds=_number("LLM_TIMEOUT_SECONDS", 45.0, float, 1),
        llm_max_retries=_number("LLM_MAX_RETRIES", 2, minimum=0),
        retrieval_threshold_chars=_number("RETRIEVAL_THRESHOLD_CHARS", 30_000, minimum=1000),
        retrieval_top_k=_number("RETRIEVAL_TOP_K", 8, minimum=1),
        cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
    )

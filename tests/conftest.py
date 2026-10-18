import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_llm_client
from app.core.config import PROVIDERS, get_settings
from app.main import app
from app.services.llm_service import LLMClient
from tests.helpers import FakeProvider

SETTINGS_VARS = [
    "AI_PROVIDER", "MAX_UPLOAD_MB", "MAX_DOCUMENT_CHARS", "CHUNK_SIZE", "CHUNK_OVERLAP",
    "LLM_TIMEOUT_SECONDS", "LLM_MAX_RETRIES", "RETRIEVAL_THRESHOLD_CHARS", "RETRIEVAL_TOP_K",
    "OLLAMA_BASE_URL", "CORS_ORIGINS",
] + [f"{name.upper()}_{kind}" for name in PROVIDERS for kind in ("API_KEY", "MODEL")]


@pytest.fixture(autouse=True)
def clean_settings(monkeypatch):
    # ignore the developer's own .env so tests behave the same everywhere
    for var in SETTINGS_VARS:
        monkeypatch.delenv(var, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def use_fake(client):
    def install(*replies):
        provider = FakeProvider(replies)
        app.dependency_overrides[get_llm_client] = lambda: LLMClient(provider)
        return provider

    return install

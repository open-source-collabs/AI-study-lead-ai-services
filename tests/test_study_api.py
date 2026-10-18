from app.api import deps
from app.api.deps import get_llm_client
from app.core.config import get_settings
from app.main import app
from app.services.llm_service import LLMClient
from tests.helpers import FakeProvider, doc

NOTES = doc("Classification predicts a category.", "Regression predicts a number.")
URL = "/api/v1/study"


def post(client, path, body=None, **kwargs):
    return client.post(f"{URL}/{path}", json=body or {"document": NOTES}, **kwargs)


def test_health(client):
    assert client.get("/api/v1/health").json()["status"] == "ok"


def test_summary_drops_invalid_pages(client, use_fake):
    use_fake({"summary": "Classification predicts categories.", "source_pages": [1, 99]})
    body = post(client, "summaries").json()
    assert body["source_pages"] == [1]
    assert (body["provider"], body["model"]) == ("fake", "fake-model")
    assert len(body["document_hash"]) == 64


def test_document_hash(client, use_fake):
    use_fake({"summary": "A long enough summary.", "source_pages": []})
    first = post(client, "summaries").json()["document_hash"]
    renamed = post(client, "summaries", {"document": {**NOTES, "title": "Other title"}}).json()["document_hash"]
    edited = post(client, "summaries", {"document": doc("Changed text.", "Regression predicts a number.")}).json()
    assert first == renamed and first != edited["document_hash"]


def test_flashcards_bare_list(client, use_fake):
    use_fake([{"question": "What does classification predict?", "answer": "A category", "source_pages": [2, 2, 50]}])
    cards = post(client, "flashcards").json()["cards"]
    assert cards[0]["source_pages"] == [2]


def test_quiz_returns_questions(client, use_fake):
    question = {
        "question": "What does regression predict?", "options": ["A number", "A label"],
        "answer_index": 0, "explanation": "It predicts numbers.", "source_pages": [2],
    }
    use_fake({"questions": [question, question]})
    assert len(post(client, "quizzes?question_count=1").json()["questions"]) == 1


def test_quiz_bad_answer_index(client, use_fake):
    bad = {"question": "Q?? ok", "options": ["A", "B"], "answer_index": 5, "explanation": "x"}
    provider = use_fake({"questions": [bad]})
    assert post(client, "quizzes").status_code == 502
    assert len(provider.prompts) == 2


def test_quiz_count_is_validated(client, use_fake):
    use_fake({"questions": []})
    assert post(client, "quizzes?question_count=0").status_code == 422
    assert post(client, "quizzes?question_count=31").status_code == 422


def test_bad_json_is_retried_once(client, use_fake):
    provider = use_fake("sorry, no json", {"summary": "A valid summary here.", "source_pages": [1]})
    assert post(client, "summaries").status_code == 200
    assert len(provider.prompts) == 2


MAP = [
    {"id": "n1", "label": "ML", "parent_id": None, "source_pages": [1]},
    {"id": "n2", "label": "Classification", "parent_id": "n1", "source_pages": [1, 9]},
    {"id": "n3", "label": "Regression", "parent_id": "n1", "source_pages": [2]},
]


def test_mind_map(client, use_fake):
    use_fake({"nodes": MAP})
    body = post(client, "mindmap").json()
    assert body["root_id"] == "n1" and len(body["nodes"]) == 3
    assert body["nodes"][1]["source_pages"] == [1]


def test_mind_map_must_be_a_proper_tree(client, use_fake):
    two_roots = [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]
    loop = [
        {"id": "r", "label": "Root"},
        {"id": "a", "label": "A", "parent_id": "b"},
        {"id": "b", "label": "B", "parent_id": "a"},
    ]
    orphan = [{"id": "r", "label": "Root"}, {"id": "a", "label": "A", "parent_id": "ghost"}]
    duplicate = [{"id": "r", "label": "Root"}, {"id": "r", "label": "Again", "parent_id": "r"}]
    for nodes in (two_roots, loop, orphan, duplicate):
        use_fake({"nodes": nodes})
        assert post(client, "mindmap").status_code == 502


def test_plan_drops_extra_days(client, use_fake):
    day = lambda n: {"day": n, "focus": f"Topic {n}", "tasks": ["Read", "Test yourself"], "minutes": 30, "source_pages": [1]}
    use_fake({"days": [day(3), day(1), day(2), day(9)]})
    body = post(client, "plan", {"document": NOTES, "days": 3, "minutes_per_day": 30, "goal": "pass the exam"}).json()
    assert [d["day"] for d in body["days"]] == [1, 2, 3]


def test_study_plan_input_limits(client, use_fake):
    use_fake({"days": []})
    assert post(client, "plan", {"document": NOTES, "days": 0}).status_code == 422
    assert post(client, "plan", {"document": NOTES, "minutes_per_day": 5}).status_code == 422


def test_ask_sends_a_short_document_whole(client, use_fake):
    provider = use_fake({"answer": "A category.", "source_pages": [1]})
    body = post(client, "ask", {"document": NOTES, "question": "What does classification predict?"}).json()
    assert body["retrieval_used"] is False and body["source_pages"] == [1]
    assert "Regression predicts a number" in provider.prompts[0]


def long_document():
    filler = " ".join(f"filler{i}" for i in range(60))
    pages = [f"{filler} page {i}" for i in range(1, 6)]
    pages[3] = "Quick sort picks a pivot and partitions the array. " + filler
    return doc(*pages)


def test_ask_long_document_uses_retrieval(client, use_fake, monkeypatch):
    monkeypatch.setenv("RETRIEVAL_THRESHOLD_CHARS", "1000")
    monkeypatch.setenv("CHUNK_SIZE", "400")
    monkeypatch.setenv("CHUNK_OVERLAP", "0")
    monkeypatch.setenv("RETRIEVAL_TOP_K", "2")
    get_settings.cache_clear()
    provider = use_fake({"answer": "It picks a pivot.", "source_pages": [4, 1]})
    body = post(client, "ask", {"document": long_document(), "question": "How does quick sort pick a pivot?"}).json()
    assert body["retrieval_used"] is True
    assert "pivot" in provider.prompts[0]
    assert len(provider.prompts[0]) < 2500
    assert body["source_pages"] == [4]


def test_ask_with_no_match_skips_the_model(client, use_fake, monkeypatch):
    monkeypatch.setenv("RETRIEVAL_THRESHOLD_CHARS", "1000")
    get_settings.cache_clear()
    provider = use_fake({"answer": "unused", "source_pages": []})
    body = post(client, "ask", {"document": long_document(), "question": "quantum entanglement?"}).json()
    assert body["retrieval_used"] is True and "could not be found" in body["answer"]
    assert provider.prompts == []


def test_size_limit(client, use_fake, monkeypatch):
    monkeypatch.setenv("MAX_DOCUMENT_CHARS", "1000")
    get_settings.cache_clear()
    use_fake({"summary": "unused summary", "source_pages": []})
    assert post(client, "summaries", {"document": doc("x" * 1001)}).status_code == 413


def test_provider_failure_is_a_502(client):
    from app.services.errors import LLMProviderError

    class Broken(FakeProvider):
        async def generate(self, prompt):
            raise LLMProviderError("groq request failed (401): bad key", status_code=401)

    app.dependency_overrides[get_llm_client] = lambda: LLMClient(Broken([""]))
    response = post(client, "summaries")
    assert response.status_code == 502 and "bad key" in response.json()["detail"]


def test_missing_key(client):
    response = post(client, "summaries")
    assert response.status_code == 503
    assert "X-AI-Key" in response.json()["detail"]


def test_provider_from_headers(client, monkeypatch):
    captured = {}

    def fake_build(name, settings, api_key=None, model=None, **kwargs):
        captured.update(name=name, api_key=api_key, model=model)
        return FakeProvider([{"summary": "A valid summary here.", "source_pages": []}], name=name, model=model)

    monkeypatch.setattr(deps, "build_provider", fake_build)
    headers = {"X-AI-Provider": "OpenRouter", "X-AI-Key": "student-key", "X-AI-Model": "vendor/some-model"}
    body = post(client, "summaries", headers=headers).json()
    assert captured == {"name": "openrouter", "api_key": "student-key", "model": "vendor/some-model"}
    assert body["provider"] == "openrouter"
    assert "student-key" not in str(body)


def test_bad_headers(client):
    assert post(client, "summaries", headers={"X-AI-Provider": "nope"}).status_code == 422
    headers = {"X-AI-Provider": "ollama", "X-AI-Model": "../../etc"}
    assert post(client, "summaries", headers=headers).status_code == 422
    headers = {"X-AI-Provider": "ollama", "X-AI-Model": "bad model!"}
    assert post(client, "summaries", headers=headers).status_code == 422

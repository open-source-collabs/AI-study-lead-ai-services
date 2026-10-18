from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.schemas.document import ExtractedPage
from app.services.document_service import chunk_pages, hash_pages
from tests.helpers import doc, make_pdf

client = TestClient(app)


def upload(content: bytes, name: str = "notes.pdf"):
    return client.post("/api/v1/documents/extract", files={"file": (name, content, "application/pdf")})


def test_extracts_real_text_page_by_page():
    response = upload(make_pdf(["Quick sort picks a pivot.", "Merge sort needs extra memory."]))
    body = response.json()
    assert response.status_code == 200
    assert body["page_count"] == 2 and body["text_page_count"] == 2
    assert "pivot" in body["pages"][0]["text"]
    assert "Merge sort" in body["pages"][1]["text"]
    assert body["warnings"] == []


def test_blank_page_gives_a_warning():
    body = upload(make_pdf(["Some text.", ""])).json()
    assert body["text_page_count"] == 1
    assert "no selectable text" in body["warnings"][0]


def test_text_hash_matches_pages():
    body = upload(make_pdf(["Alpha beta.", "Gamma delta."])).json()
    pages = [ExtractedPage(**page) for page in body["pages"]]
    assert body["text_hash"] == hash_pages(pages)


def test_rejects_bad_files():
    assert upload(b"%PDF-1.4", "notes.txt").status_code == 415
    assert upload(b"this is not a pdf").status_code == 422
    assert upload(b"").status_code == 422


def test_rejects_oversized_upload(monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()
    assert upload(b"%PDF-" + b"0" * (1024 * 1024 + 1)).status_code == 413


def test_chunks_endpoint():
    response = client.post("/api/v1/documents/chunks", json=doc("one two three", "four five six"))
    assert response.status_code == 200
    assert [chunk["start_page"] for chunk in response.json()] == [1, 2]


def test_rejects_empty_and_duplicate_pages():
    assert client.post("/api/v1/documents/chunks", json=doc("   ", "")).status_code == 422
    repeated = {"pages": [{"page_number": 1, "text": "a"}, {"page_number": 1, "text": "b"}]}
    assert client.post("/api/v1/documents/chunks", json=repeated).status_code == 422


def test_chunks_cut_on_word_boundaries():
    text = " ".join(f"word{i}" for i in range(400))
    words = set(text.split())
    chunks = chunk_pages([ExtractedPage(page_number=1, text=text)], 200, 40)
    assert len(chunks) > 5
    for chunk in chunks:
        pieces = chunk.text.split()
        assert pieces[0] in words and pieces[-1] in words
        assert chunk.character_count <= 200


def test_chunks_overlap_and_cover_the_text():
    text = " ".join(f"w{i}" for i in range(300))
    chunks = chunk_pages([ExtractedPage(page_number=1, text=text)], 150, 30)
    assert chunks[0].text.split()[0] == "w0"
    assert chunks[-1].text.split()[-1] == "w299"
    for before, after in zip(chunks, chunks[1:]):
        assert set(before.text.split()) & set(after.text.split())


def test_chunks_stay_on_one_page():
    pages = [ExtractedPage(page_number=3, text="a b c d e f"), ExtractedPage(page_number=1, text="x y z")]
    chunks = chunk_pages(pages, 5, 0)
    assert chunks[0].start_page == 1
    assert all(chunk.start_page == chunk.end_page for chunk in chunks)

# AI Study Companion: AI Service

FastAPI service for the AI part of the Study Companion. It reads a PDF into page-by-page text, and from that text it can make a summary, flashcards, a quiz, a mind map or a study plan, or answer a question from the notes. Results include the pages they came from.

It works with Gemini, Groq, OpenRouter, OpenAI or a local model through Ollama, and a student can send their own API key. The service doesn't store anything.

## Endpoints

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/v1/health` | health check |
| POST | `/api/v1/documents/extract` | PDF in, text per page out |
| POST | `/api/v1/documents/chunks` | split page text into chunks |
| POST | `/api/v1/study/summaries` | summary |
| POST | `/api/v1/study/flashcards` | flashcards |
| POST | `/api/v1/study/quizzes?question_count=10` | multiple-choice quiz, 1 to 30 questions |
| POST | `/api/v1/study/mindmap` | mind map as a tree of nodes |
| POST | `/api/v1/study/plan` | day-by-day study plan |
| POST | `/api/v1/study/ask` | answer a question from the notes |

Swagger docs are at `/docs` when the server is running.

## Setup

Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # Windows: copy .env.example .env
```

Put a key in `.env` (for example `GEMINI_API_KEY`) and start the server:

```bash
python -m uvicorn app.main:app --reload
```

The server doesn't reload `.env`, so restart it after editing the file.

Tests don't need a key or network, they use a fake model:

```bash
python -m pytest -q
```

## Usage

Upload a PDF to `/documents/extract` (form field `file`). The response has the text of each page and a `text_hash`:

```json
{
  "filename": "lecture.pdf",
  "page_count": 2,
  "text_hash": "9f2c...",
  "pages": [
    {"page_number": 1, "text": "..."},
    {"page_number": 2, "text": "..."}
  ],
  "warnings": []
}
```

The study endpoints take those pages inside a `document` field:

```json
{
  "document": {
    "title": "Week 1 Lecture",
    "pages": [{"page_number": 1, "text": "..."}]
  },
  "level": "beginner",
  "language": "English"
}
```

`level` can be `beginner`, `intermediate` or `advanced`. `language` is optional. `/study/plan` also accepts `days` (default 7), `minutes_per_day` (default 60) and `goal`. `/study/ask` takes `document` and `question`.

Every response has `provider`, `model` and `document_hash`. The hash is built from the page text only, and it equals the `text_hash` from extraction, so the backend can use it to recognise a document it has already processed.

The mind map response has a `root_id` and a list of `nodes`, each with `id`, `label` and `parent_id` (null for the root).

### Choosing the provider

Without headers the service uses `AI_PROVIDER` and the keys from `.env`. A request can override that with three headers: `X-AI-Provider` (`gemini`, `groq`, `openrouter`, `openai` or `ollama`), `X-AI-Key` and `X-AI-Model`. The key is used for that request and isn't stored or logged. Ollama doesn't need one.

## Configuration

All of these go in `.env`. See `.env.example`.

| Variable | Default |
|---|---|
| `AI_PROVIDER` | `gemini` |
| `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `OPENAI_API_KEY` | empty |
| `GEMINI_MODEL` | `gemini-3.8-flash` |
| `GROQ_MODEL` | `openai/gpt-oss-120b` |
| `OPENROUTER_MODEL`, `OPENAI_MODEL`, `OLLAMA_MODEL` | empty, you pick one |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` |
| `MAX_UPLOAD_MB` | 10 |
| `MAX_DOCUMENT_CHARS` | 180000 |
| `LLM_TIMEOUT_SECONDS` | 45 |
| `LLM_MAX_RETRIES` | 2 |
| `CHUNK_SIZE`, `CHUNK_OVERLAP` | 1200, 180 |
| `RETRIEVAL_THRESHOLD_CHARS` | 30000 |
| `RETRIEVAL_TOP_K` | 8 |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173` |

Local models are slow, so raise `LLM_TIMEOUT_SECONDS` if you use Ollama. If a call fails with "model not found", the model ID isn't available for that key.

Errors: 413 for a file or text over the limit, 415 for a non-PDF upload, 422 for bad input, 502 when the provider fails or returns something unusable twice in a row, and 503 when there's no key or model for the chosen provider.

## Limits

- No OCR. Scanned pages, and text inside images, are skipped.
- `/ask` on a document over `RETRIEVAL_THRESHOLD_CHARS` picks chunks by matching words, not meaning, so a question worded differently from the notes can miss. The other endpoints always send the whole document, up to `MAX_DOCUMENT_CHARS`.
- Page numbers that the model makes up are dropped, but the service can't check that a cited page really supports the answer.
- No authentication or rate limiting. Don't expose it directly to the internet.
- Requests are synchronous, so long documents on slow models take a while.

More on how the code is organised in [ARCHITECTURE.md](ARCHITECTURE.md).

# Architecture

The service keeps no state. Each request carries everything it needs.

```
PDF -> /documents/extract -> pages + text_hash
                                  |
        (caller keeps the pages)  v
  /study/summaries | flashcards | quizzes | mindmap | plan | ask
                                  |
  choose provider -> build prompt -> call model -> parse JSON -> validate -> drop invalid pages
```

A study request goes through `get_llm_client`, which builds a provider from the `X-AI-*` headers or from `.env`. The route builds a prompt from `services/prompts.py` and passes it to `LLMClient.generate` together with a function that validates the reply. If the reply isn't valid JSON, or fails validation, the model is asked once more. Errors from the AI layer become HTTP responses in `api/errors.py`, which is why the routes have no try/except.

## Layout

```
app/
  main.py                 app, CORS, error handlers
  core/config.py          settings from .env
  api/
    deps.py               provider per request, size limit
    errors.py             error type to HTTP status
    routes/               health, documents, study
  schemas/                request and response models
  services/
    document_service.py   PDF extraction, chunking, document hash
    retrieval.py          BM25 search over chunks
    prompts.py            one prompt per feature
    providers.py          Gemini and OpenAI-style providers
    llm_service.py        LLMClient and JSON parsing
    errors.py             exception types
tests/
```

## Notes

A provider only turns a prompt into text. `GeminiProvider` calls `generateContent`. `OpenAICompatibleProvider` calls `/chat/completions` and covers Groq, OpenRouter, OpenAI and Ollama, which only differ in base URL. Another OpenAI-style provider needs one line in `OPENAI_STYLE_URLS` and an entry in `PROVIDERS`. Azure OpenAI and Hugging Face use different request formats and would need their own class.

The student's key comes in through `X-AI-Key` and only lives in the provider object for that request. Callers can choose a provider and a model but not a URL, so a request can't point the service at another server. Ollama's URL is the one that can change, and it comes from `.env`.

Both providers are asked for JSON output (Gemini through `responseMimeType`, the others through `response_format`). If a model rejects `response_format` with a 400, the call is repeated without it. The parser still copes with code fences and short intros, since not every model follows the instruction.

Rate limits (429), 5xx errors and network failures are retried with a short wait. Other 4xx errors, like a wrong key, are not.

`chunk_pages` splits each page on its own, so a chunk always belongs to one page, and chunks start and end on word boundaries.

For `/ask`, a short document goes into the prompt whole. A long one is chunked and ranked against the question with BM25, and only the best `RETRIEVAL_TOP_K` chunks are sent. This needs no model or vector store, but it only matches words. If no chunk shares a word with the question, the answer is "not found in the provided notes" and the model isn't called.

`hash_pages` hashes the page text. Extraction returns it as `text_hash` and every study response returns it as `document_hash`, so the backend can tell when it has already generated something for a document.

The mind map comes back as nodes with a `parent_id`. The schema checks for exactly one root, unique ids, existing parents and no loops. A reply that fails is retried once.

Provider tests use `httpx.MockTransport`. API tests replace the provider with a fake through FastAPI dependency overrides. The PDF tests build a real PDF, so extraction runs on actual PDF bytes.

Users, file storage, saved results, history and progress tracking belong to the backend that calls this service.

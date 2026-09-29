# AI Study Companion - AI Services

Independent FastAPI service for AI processing in AI Study Companion.

## Current status

Implemented: FastAPI app, `GET /`, `GET /health`, generated API docs and a health test.

Planned: provider integration, PDF/text processing, summaries, flashcards, quizzes and
study-material-grounded Q&A. None of these planned features works in this starter.

The separate Node/Express backend owns study workflow, users, materials, storage and
progress. This service will own AI processing. The backend ZIP reviewed for this
starter was a **feature branch** with only foundation and database plumbing; its
uploads and AI integration were still planned. Check the team's current backend
branch before finalizing integration.

## Folder structure

```text
AI-study-lead-ai-services/
├── app/
│   ├── __init__.py
│   ├── main.py             # FastAPI application
│   └── api/
│       ├── __init__.py
│       ├── router.py       # Connects feature routes
│       └── routes/
│           ├── __init__.py
│           └── health.py   # GET /health
├── tests/
│   └── test_health.py
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

Add `providers/`, `services/`, `schemas/` and document-processing modules when
the corresponding feature and its interface are agreed on; empty files are not
necessary for this milestone.

## Requirements

Python 3.10 or newer. A network connection is needed for the initial package
installation. No API keys or database are needed for the health endpoint.

## Run locally on Windows (PowerShell)

Open PowerShell inside this folder and run:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

You can skip activating the environment because these commands call its Python
directly. If `py -3` is unavailable, use `python -m venv .venv` instead.

Open http://127.0.0.1:8000/health and http://127.0.0.1:8000/docs.
To run tests in a separate PowerShell window from this folder:

```powershell
.venv\Scripts\python.exe -m pytest -q
```

The expected health result is:

```json
{"success": true, "service": "ai-study-lead-ai-services", "status": "ok"}
```

The backend runs on port 3000 by default; this service runs on port 8000 by
default. These are two independent applications.

## Decisions to make with the backend team before adding AI routes

1. What does the AI service receive: extracted text, a short-lived document URL,
   or PDF bytes? Who owns extraction and document access?
2. Define the endpoint names, request/response JSON, input size limits, errors
   and timeout/retry behavior. Agree whether the backend needs synchronous
   responses or a job/status flow for longer processing.
3. Decide how the backend authenticates its calls and how user-provided provider
   credentials are passed or accessed without logging them.
4. Select the first provider while keeping feature logic independent of its SDK.

The reviewed backend has no live AI contract yet. Do not treat these questions
or an example endpoint as an approved team decision.

## Adding this starter to the team's empty AI repository

Clone the team repository, copy the **contents** of this folder into the clone
(including the hidden `.gitignore` and `.env.example`), run the commands above,
and make a focused commit. Do not copy `.venv` into Git. Confirm the repository
URL and team branch/PR rules before pushing.

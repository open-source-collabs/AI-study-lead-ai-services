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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_error_handlers
from app.api.router import api_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="AI Study Companion: AI Service",
    description=(
        "Turns PDF notes into summaries, flashcards, quizzes, mind maps, study plans and "
        "answers grounded in the notes. Stateless: nothing is stored."
    ),
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
register_error_handlers(app)
app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["health"])
async def root() -> dict[str, str]:
    return {"message": "AI Study Companion AI service is running.", "docs": "/docs"}

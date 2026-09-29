from fastapi import FastAPI

from app.api.router import api_router

app = FastAPI(
    title="AI Study Companion - AI Services",
    description="Independent AI processing service for AI Study Companion.",
    version="0.1.0",
)
app.include_router(api_router)


@app.get("/", tags=["Service"])
def root() -> dict[str, str]:
    return {
        "message": "AI Study Companion - AI Services",
        "docs": "/docs",
        "health": "/health",
    }

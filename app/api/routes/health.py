from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check() -> dict[str, str | bool]:
    """Report that the AI service can accept HTTP requests."""
    return {
        "success": True,
        "service": "ai-study-lead-ai-services",
        "status": "ok",
    }

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.services.document_service import DocumentProcessingError
from app.services.errors import InvalidModelOutput, LLMConfigurationError, LLMProviderError

STATUS_BY_ERROR = {
    LLMConfigurationError: 503,
    LLMProviderError: 502,
    InvalidModelOutput: 502,
    DocumentProcessingError: 422,
}


def _handler(status_code: int):
    async def handle(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handle


def register_error_handlers(app: FastAPI) -> None:
    for error_type, status_code in STATUS_BY_ERROR.items():
        app.add_exception_handler(error_type, _handler(status_code))

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.api.deps import enforce_size_limit
from app.core.config import get_settings
from app.schemas.document import DocumentChunk, DocumentContext, DocumentExtractionResponse
from app.services.document_service import chunk_pages, extract_pdf

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/extract", response_model=DocumentExtractionResponse, summary="Extract text from a PDF")
async def extract_document(file: UploadFile = File(...)) -> DocumentExtractionResponse:
    settings = get_settings()
    filename = (file.filename or "upload.pdf").strip()
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(415, "Upload a .pdf file.")
    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            413,
            f"PDF is over the {settings.max_upload_mb} MB upload limit.",
        )
    return extract_pdf(content, filename, settings.max_document_chars)


@router.post("/chunks", response_model=list[DocumentChunk], summary="Split page text into chunks")
async def create_chunks(document: DocumentContext) -> list[DocumentChunk]:
    settings = get_settings()
    enforce_size_limit(document)
    return chunk_pages(document.pages, settings.chunk_size, settings.chunk_overlap)

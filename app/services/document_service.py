import hashlib
from io import BytesIO

from pypdf import PdfReader

from app.schemas.document import DocumentChunk, DocumentExtractionResponse, ExtractedPage


class DocumentProcessingError(ValueError):
    pass


def hash_pages(pages: list[ExtractedPage]) -> str:
    # same pages give the same hash whatever the title, so the backend can use it as a cache key
    digest = hashlib.sha256()
    for page in sorted(pages, key=lambda item: item.page_number):
        digest.update(f"{page.page_number}\x1f{page.text.strip()}\x1e".encode())
    return digest.hexdigest()


def extract_pdf(pdf_bytes: bytes, filename: str, max_document_chars: int) -> DocumentExtractionResponse:
    if not pdf_bytes:
        raise DocumentProcessingError("The uploaded file is empty.")
    if not pdf_bytes.startswith(b"%PDF-"):
        raise DocumentProcessingError("The file does not appear to be a valid PDF.")

    pages: list[ExtractedPage] = []
    total_chars = 0
    try:
        reader = PdfReader(BytesIO(pdf_bytes), strict=False)
        if reader.is_encrypted and not reader.decrypt(""):
            raise DocumentProcessingError("This PDF is password-protected. Upload an unlocked PDF.")
        for number, page in enumerate(reader.pages, start=1):
            try:
                text = (page.extract_text() or "").strip()
            except Exception as exc:
                raise DocumentProcessingError(f"Could not read page {number}. The PDF may be damaged.") from exc
            total_chars += len(text)
            if total_chars > max_document_chars:
                raise DocumentProcessingError(
                    f"The PDF text is over the {max_document_chars:,}-character limit."
                )
            pages.append(ExtractedPage(page_number=number, text=text))
    except DocumentProcessingError:
        raise
    except Exception as exc:
        raise DocumentProcessingError("The PDF could not be read. It may be damaged or unsupported.") from exc

    text_pages = sum(1 for page in pages if page.text)
    warnings = []
    if not pages:
        warnings.append("This PDF has no pages.")
    elif text_pages == 0:
        warnings.append("No selectable text found. This may be a scanned PDF, and OCR is not supported.")
    elif text_pages < len(pages):
        warnings.append("Some pages have no selectable text. They may be scans, images or blank.")

    return DocumentExtractionResponse(
        filename=filename,
        page_count=len(pages),
        text_page_count=text_pages,
        character_count=total_chars,
        text_hash=hash_pages(pages),
        pages=pages,
        warnings=warnings,
    )


def chunk_pages(pages: list[ExtractedPage], chunk_size: int, chunk_overlap: int) -> list[DocumentChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if not 0 <= chunk_overlap < chunk_size:
        raise ValueError("chunk_overlap must be zero or more, and smaller than chunk_size")

    chunks: list[DocumentChunk] = []
    for page in sorted(pages, key=lambda item: item.page_number):
        text = page.text.strip()
        start = 0
        while text and start < len(text):
            end = min(start + chunk_size, len(text))
            if end < len(text):
                # Cut at a space near the end of the window if there is one.
                space = text.rfind(" ", start + chunk_size * 3 // 4, end)
                if space > start:
                    end = space
            piece = text[start:end].strip()
            if piece:
                number = len(chunks) + 1
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"p{page.page_number}-c{number}",
                        chunk_number=number,
                        start_page=page.page_number,
                        end_page=page.page_number,
                        text=piece,
                        character_count=len(piece),
                    )
                )
            if end >= len(text):
                break
            start = _word_start(text, max(start + 1, end - chunk_overlap), end)
    return chunks


def _word_start(text: str, pos: int, limit: int) -> int:
    # if pos is inside a word, move forward to the start of the next one
    if text[pos - 1].isspace() or text[pos].isspace():
        return pos
    i = pos
    while i < limit and not text[i].isspace():
        i += 1
    while i < limit and text[i].isspace():
        i += 1
    return i if i < limit else pos

from pydantic import BaseModel, Field, field_validator, model_validator


class ExtractedPage(BaseModel):
    page_number: int = Field(ge=1)
    text: str


class DocumentExtractionResponse(BaseModel):
    filename: str
    page_count: int = Field(ge=0)
    text_page_count: int = Field(ge=0)
    character_count: int = Field(ge=0)
    text_hash: str
    pages: list[ExtractedPage]
    warnings: list[str] = Field(default_factory=list)


class DocumentContext(BaseModel):
    title: str = Field(default="Untitled document", max_length=250)
    pages: list[ExtractedPage] = Field(min_length=1, max_length=500)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return value.strip() or "Untitled document"

    @model_validator(mode="after")
    def check_pages(self) -> "DocumentContext":
        if not any(page.text.strip() for page in self.pages):
            raise ValueError("The document has no text. It may be a scan, and OCR is not supported.")
        numbers = [page.page_number for page in self.pages]
        if len(numbers) != len(set(numbers)):
            raise ValueError("Page numbers must be unique")
        return self


class DocumentChunk(BaseModel):
    chunk_id: str
    chunk_number: int = Field(ge=1)
    start_page: int = Field(ge=1)
    end_page: int = Field(ge=1)
    text: str
    character_count: int = Field(ge=0)

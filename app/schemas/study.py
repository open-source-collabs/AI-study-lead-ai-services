from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.schemas.document import DocumentContext


def _unique_pages(pages: list[int]) -> list[int]:
    return sorted({page for page in pages if page >= 1})


PageList = Annotated[list[int], AfterValidator(_unique_pages)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]


class StudyRequest(BaseModel):
    document: DocumentContext
    level: Literal["beginner", "intermediate", "advanced"] = "beginner"
    language: str = Field(default="same as the source notes", max_length=80)


class StudyPlanRequest(StudyRequest):
    days: int = Field(default=7, ge=1, le=60)
    minutes_per_day: int = Field(default=60, ge=10, le=480)
    goal: str | None = Field(default=None, max_length=300)


class AskRequest(BaseModel):
    document: DocumentContext
    question: str = Field(min_length=2, max_length=2000)


class StudyOutput(BaseModel):
    provider: str
    model: str
    document_hash: str


class SummaryResponse(StudyOutput):
    title: str
    summary: str
    source_pages: list[int]


class Flashcard(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    answer: str = Field(min_length=1, max_length=3000)
    source_pages: PageList = Field(default_factory=list)


class FlashcardsResponse(StudyOutput):
    title: str
    cards: list[Flashcard]


class QuizQuestion(BaseModel):
    question: str = Field(min_length=3, max_length=1200)
    options: list[str] = Field(min_length=2, max_length=6)
    answer_index: int = Field(ge=0)
    explanation: str = Field(min_length=1, max_length=3000)
    source_pages: PageList = Field(default_factory=list)

    @field_validator("options")
    @classmethod
    def clean_options(cls, value: list[str]) -> list[str]:
        cleaned = [option.strip() for option in value]
        if any(not option for option in cleaned):
            raise ValueError("Quiz options cannot be empty")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("Quiz options must be distinct")
        return cleaned

    @model_validator(mode="after")
    def answer_in_range(self) -> "QuizQuestion":
        if self.answer_index >= len(self.options):
            raise ValueError("answer_index is outside the options list")
        return self


class QuizResponse(StudyOutput):
    title: str
    questions: list[QuizQuestion]


class MindMapNode(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=150)
    parent_id: str | None = None
    source_pages: PageList = Field(default_factory=list)


class MindMapData(BaseModel):
    nodes: list[MindMapNode] = Field(min_length=2, max_length=80)

    @model_validator(mode="after")
    def check_tree(self) -> "MindMapData":
        parents = {node.id: node.parent_id for node in self.nodes}
        if len(parents) != len(self.nodes):
            raise ValueError("Node ids must be unique")
        if sum(1 for parent in parents.values() if parent is None) != 1:
            raise ValueError("A mind map needs exactly one root node")
        for node_id in parents:
            seen: set[str] = set()
            current: str | None = node_id
            while current is not None:
                if current in seen:
                    raise ValueError("The mind map contains a loop")
                if current not in parents:
                    raise ValueError(f"Unknown parent id '{current}'")
                seen.add(current)
                current = parents[current]
        return self

    @property
    def root_id(self) -> str:
        return next(node.id for node in self.nodes if node.parent_id is None)


class MindMapResponse(StudyOutput):
    title: str
    root_id: str
    nodes: list[MindMapNode]


class PlanDay(BaseModel):
    day: int = Field(ge=1)
    focus: str = Field(min_length=1, max_length=300)
    tasks: list[ShortText] = Field(min_length=1, max_length=10)
    minutes: int = Field(ge=1, le=720)
    source_pages: PageList = Field(default_factory=list)


class StudyPlanResponse(StudyOutput):
    title: str
    days: list[PlanDay]


class AskResponse(StudyOutput):
    answer: str
    source_pages: list[int] = Field(default_factory=list)
    retrieval_used: bool = False

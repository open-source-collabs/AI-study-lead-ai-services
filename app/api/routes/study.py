from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, model_validator

from app.api.deps import enforce_size_limit, get_llm_client
from app.core.config import get_settings
from app.schemas.document import DocumentContext
from app.schemas.study import (
    AskRequest,
    AskResponse,
    Flashcard,
    FlashcardsResponse,
    MindMapData,
    MindMapResponse,
    PlanDay,
    QuizQuestion,
    QuizResponse,
    StudyPlanRequest,
    StudyPlanResponse,
    StudyRequest,
    SummaryResponse,
)
from app.services import prompts
from app.services.document_service import chunk_pages, hash_pages
from app.services.errors import InvalidModelOutput
from app.services.llm_service import LLMClient
from app.services.retrieval import select_chunks

router = APIRouter(prefix="/study", tags=["study tools"])


class _Summary(BaseModel):
    summary: str = Field(min_length=10, max_length=20000)
    source_pages: list[int] = Field(default_factory=list)


class _Answer(BaseModel):
    answer: str = Field(min_length=1, max_length=12000)
    source_pages: list[int] = Field(default_factory=list)


class _Cards(BaseModel):
    cards: list[Flashcard] = Field(min_length=1)


class _Questions(BaseModel):
    questions: list[QuizQuestion] = Field(min_length=1)


class _Plan(BaseModel):
    days: list[PlanDay] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_days(self) -> "_Plan":
        numbers = [day.day for day in self.days]
        if len(numbers) != len(set(numbers)):
            raise ValueError("Day numbers must be unique")
        return self


def _list_parser(model: type[BaseModel], key: str):
    # models sometimes return a bare list instead of {"key": [...]}
    def parse(data: Any) -> Any:
        return model.model_validate({key: data} if isinstance(data, list) else data)

    return parse


def _meta(client: LLMClient, document: DocumentContext) -> dict[str, str]:
    return {
        "provider": client.info.provider,
        "model": client.info.model,
        "document_hash": hash_pages(document.pages),
    }


def _keep_valid(pages: list[int], allowed: set[int]) -> list[int]:
    return sorted({page for page in pages if page in allowed})


def _restrict(items: list, allowed: set[int]) -> list:
    return [
        item.model_copy(update={"source_pages": _keep_valid(item.source_pages, allowed)})
        for item in items
    ]


def _page_numbers(document: DocumentContext) -> set[int]:
    return {page.page_number for page in document.pages}


@router.post("/summaries", response_model=SummaryResponse)
async def create_summary(request: StudyRequest, client: LLMClient = Depends(get_llm_client)):
    document = request.document
    enforce_size_limit(document)
    prompt = prompts.summary_prompt(
        document.title, prompts.notes_from_document(document), request.level, request.language
    )
    result = await client.generate(prompt, _Summary.model_validate)
    return SummaryResponse(
        title=document.title,
        summary=result.summary,
        source_pages=_keep_valid(result.source_pages, _page_numbers(document)),
        **_meta(client, document),
    )


@router.post("/flashcards", response_model=FlashcardsResponse)
async def create_flashcards(request: StudyRequest, client: LLMClient = Depends(get_llm_client)):
    document = request.document
    enforce_size_limit(document)
    prompt = prompts.flashcards_prompt(
        document.title, prompts.notes_from_document(document), request.level, request.language
    )
    result = await client.generate(prompt, _list_parser(_Cards, "cards"))
    return FlashcardsResponse(
        title=document.title,
        cards=_restrict(result.cards[:40], _page_numbers(document)),
        **_meta(client, document),
    )


@router.post("/quizzes", response_model=QuizResponse)
async def create_quiz(
    request: StudyRequest,
    question_count: int = Query(default=10, ge=1, le=30),
    client: LLMClient = Depends(get_llm_client),
):
    document = request.document
    enforce_size_limit(document)
    prompt = prompts.quiz_prompt(
        document.title, prompts.notes_from_document(document), request.level, request.language, question_count
    )
    result = await client.generate(prompt, _list_parser(_Questions, "questions"))
    return QuizResponse(
        title=document.title,
        questions=_restrict(result.questions[:question_count], _page_numbers(document)),
        **_meta(client, document),
    )


@router.post("/mindmap", response_model=MindMapResponse)
async def create_mind_map(request: StudyRequest, client: LLMClient = Depends(get_llm_client)):
    document = request.document
    enforce_size_limit(document)
    prompt = prompts.mindmap_prompt(
        document.title, prompts.notes_from_document(document), request.level, request.language
    )
    result = await client.generate(prompt, _list_parser(MindMapData, "nodes"))
    return MindMapResponse(
        title=document.title,
        root_id=result.root_id,
        nodes=_restrict(result.nodes, _page_numbers(document)),
        **_meta(client, document),
    )


@router.post("/plan", response_model=StudyPlanResponse)
async def create_study_plan(request: StudyPlanRequest, client: LLMClient = Depends(get_llm_client)):
    document = request.document
    enforce_size_limit(document)
    prompt = prompts.plan_prompt(
        document.title,
        prompts.notes_from_document(document),
        request.level,
        request.language,
        request.days,
        request.minutes_per_day,
        request.goal,
    )

    def parse(data: Any) -> list[PlanDay]:
        plan = _list_parser(_Plan, "days")(data)
        days = sorted((day for day in plan.days if day.day <= request.days), key=lambda day: day.day)
        if not days:
            raise InvalidModelOutput("The plan had no days in the requested range.")
        return days

    days = await client.generate(prompt, parse)
    return StudyPlanResponse(
        title=document.title,
        days=_restrict(days, _page_numbers(document)),
        **_meta(client, document),
    )


@router.post("/ask", response_model=AskResponse)
async def ask_question(request: AskRequest, client: LLMClient = Depends(get_llm_client)):
    document = request.document
    enforce_size_limit(document)
    settings = get_settings()
    meta = _meta(client, document)

    # short documents go in whole, long ones only as the chunks that match the question
    long_document = sum(len(page.text) for page in document.pages) > settings.retrieval_threshold_chars
    allowed = _page_numbers(document)
    if long_document:
        chunks = chunk_pages(document.pages, settings.chunk_size, settings.chunk_overlap)
        picked = select_chunks(chunks, request.question, settings.retrieval_top_k)
        if not picked:
            return AskResponse(answer=prompts.NOT_FOUND_ANSWER, retrieval_used=True, **meta)
        notes = prompts.notes_from_chunks(picked)
        allowed = {chunk.start_page for chunk in picked}
    else:
        notes = prompts.notes_from_document(document)

    prompt = prompts.ask_prompt(document.title, notes, request.question)
    result = await client.generate(prompt, _Answer.model_validate)
    return AskResponse(
        answer=result.answer,
        source_pages=_keep_valid(result.source_pages, allowed),
        retrieval_used=long_document,
        **meta,
    )

"""Request/response models for tutor conversations."""
import datetime as dt
import uuid

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    submission_id: uuid.UUID | None = None


class AskResponse(BaseModel):
    answer: str
    used_llm: bool
    used_rag: bool
    rag_search_available: bool
    recurring_mistakes: list[str]


class TutorMessageOut(BaseModel):
    role: str
    content: str
    created_at: dt.datetime

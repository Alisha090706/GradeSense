"""Request/response models for submitting and reviewing submissions."""
import uuid

from pydantic import BaseModel, Field


class SubmissionCreate(BaseModel):
    content: str = Field(min_length=1)
    # "python" | "java" | "cpp" | "javascript" — see agents/evaluation/schemas.py's
    # SUPPORTED_LANGUAGES. Anything else is rejected with a 400 before the pipeline runs.
    language: str = "python"


class BreakdownItemOut(BaseModel):
    category: str
    earned: float
    possible: float
    detail: str | None = None


class FlaggedPairOut(BaseModel):
    peer_student_id: str
    similarity: float
    technique: str


class SubmissionResultOut(BaseModel):
    submission_id: uuid.UUID
    exec_status: str
    score: float
    total_points: float
    breakdown: list[BreakdownItemOut]
    feedback: str
    failing_tests: list[str]
    similarity_flagged: list[FlaggedPairOut]
    pipeline_log: list[str]

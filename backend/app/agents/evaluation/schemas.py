"""Shared pydantic I/O for every LanguageRunner — moved out of the old
execution_agent.py (now a thin dispatcher, see agents/execution_agent.py)
so every runner module can import these without a circular import."""
from pydantic import BaseModel

SUPPORTED_LANGUAGES = ("python", "java", "cpp", "javascript")
DEFAULT_TIMEOUT_SECONDS = 5


class ExecutionInput(BaseModel):
    language: str
    submission_content: str
    test_cases: list[dict]
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS


class ExecutionOutput(BaseModel):
    status: str  # ok | timeout | crash
    results: list[dict] = []
    raw_error: str | None = None
    elapsed_ms: float | None = None

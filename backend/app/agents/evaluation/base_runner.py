"""LanguageRunner protocol — every language plugs into the Evaluation Agent
by implementing exactly this. See execution_agent.py for the dispatcher
that picks a runner by ExecutionInput.language."""
from abc import ABC, abstractmethod

from app.agents.evaluation.schemas import ExecutionOutput


class LanguageRunner(ABC):
    language: str

    @abstractmethod
    def run(self, submission_content: str, test_cases: list[dict], timeout_seconds: int) -> ExecutionOutput:
        ...

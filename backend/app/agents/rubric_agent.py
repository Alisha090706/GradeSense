"""
Rubric Agent — Phase 3.

Generates weighted grading criteria for an assignment. Unlike the Test
Generation path (assignment_setup_agent.py), a rubric can't be verified by
execution — there's no "run it and check" for whether "readability: 10%"
is the right weight — so this agent DOES have an offline fallback, same
shape as Feedback/Similarity/Class-Insight: a sensible, type-specific
default rubric when no LLM is configured, and an LLM-customized one
(seeded with that same default as a starting point) when one is.

Every returned rubric's weights sum to 1.0 — `_normalize` enforces this
regardless of what the model proposes, since a rubric whose weights don't
sum to 100% of the score is silently wrong in a way nothing downstream
would catch until a teacher notices scores don't add up.
"""
import json
import re

from pydantic import BaseModel

from app.agents.base import Agent
from app.agents import llm_client
from app.db.models.assignment import AssignmentType

SYSTEM_PROMPT = """You design grading rubrics for an educational assessment platform.
Given an assignment's type, title, description, subject, and a sensible starting-point
rubric, propose a refined set of weighted grading criteria tailored to THIS specific
assignment (e.g. a recursion assignment might weight "edge_cases" higher than a simple
formatting assignment would). Keep criteria names short, snake_case, and specific enough
to be gradable. Weights must be positive numbers that sum to 1.0 (they will be
re-normalized if they don't, but try to get it right). Use 3-6 criteria. Respond ONLY as
a valid JSON array, no prose outside it: [{"name": "snake_case_name", "weight": 0.0-1.0}, ...]"""

# Type-specific fallback rubrics, used both as the offline result and as the
# starting point handed to the LLM when one is configured.
DEFAULT_RUBRICS: dict[AssignmentType, list[dict]] = {
    AssignmentType.programming: [
        {"name": "correctness", "weight": 0.5},
        {"name": "efficiency", "weight": 0.15},
        {"name": "edge_cases", "weight": 0.15},
        {"name": "readability", "weight": 0.1},
        {"name": "naming", "weight": 0.05},
        {"name": "documentation", "weight": 0.05},
    ],
    AssignmentType.sql: [
        {"name": "correctness", "weight": 0.6},
        {"name": "query_efficiency", "weight": 0.2},
        {"name": "schema_understanding", "weight": 0.1},
        {"name": "readability", "weight": 0.1},
    ],
    AssignmentType.theory: [
        {"name": "conceptual_accuracy", "weight": 0.5},
        {"name": "depth_of_explanation", "weight": 0.25},
        {"name": "clarity", "weight": 0.15},
        {"name": "use_of_examples", "weight": 0.1},
    ],
    AssignmentType.mcq: [
        {"name": "correctness", "weight": 1.0},
    ],
    AssignmentType.case_study: [
        {"name": "problem_analysis", "weight": 0.3},
        {"name": "solution_quality", "weight": 0.3},
        {"name": "justification", "weight": 0.25},
        {"name": "communication", "weight": 0.15},
    ],
    AssignmentType.design: [
        {"name": "correctness_of_design", "weight": 0.35},
        {"name": "scalability_considerations", "weight": 0.25},
        {"name": "tradeoff_analysis", "weight": 0.25},
        {"name": "clarity_of_explanation", "weight": 0.15},
    ],
}


class RubricInput(BaseModel):
    title: str
    description: str = ""
    assignment_type: AssignmentType
    subject_name: str | None = None


class RubricCriterionOut(BaseModel):
    name: str
    weight: float


class RubricOutput(BaseModel):
    criteria: list[RubricCriterionOut]
    source: str  # "llm" | "default"


def _normalize(criteria: list[dict]) -> list[dict]:
    total = sum(c.get("weight", 0) for c in criteria)
    if total <= 0:
        return DEFAULT_RUBRICS[AssignmentType.programming]
    return [{"name": c["name"], "weight": round(c["weight"] / total, 3)} for c in criteria]


def _extract_json_array(text: str) -> list[dict]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    return json.loads(text)


class RubricAgent(Agent[RubricInput, RubricOutput]):
    name = "rubric_agent"

    def run(self, payload: RubricInput) -> RubricOutput:
        default = DEFAULT_RUBRICS.get(payload.assignment_type, DEFAULT_RUBRICS[AssignmentType.programming])

        if not llm_client.is_live():
            return RubricOutput(criteria=[RubricCriterionOut(**c) for c in default], source="default")

        user_prompt = (
            f"Assignment type: {payload.assignment_type.value}\n"
            f"Subject: {payload.subject_name or 'unspecified'}\n"
            f"Title: {payload.title}\n"
            f"Description: {payload.description}\n\n"
            f"Starting-point rubric for this assignment type: {default}\n\n"
            f"Propose the refined rubric now."
        )
        text = llm_client.complete(SYSTEM_PROMPT, user_prompt, max_tokens=500)
        if not text:
            return RubricOutput(criteria=[RubricCriterionOut(**c) for c in default], source="default")

        try:
            proposed = _extract_json_array(text)
            normalized = _normalize(proposed)
            return RubricOutput(criteria=[RubricCriterionOut(**c) for c in normalized], source="llm")
        except Exception:
            # Malformed model output — fall back rather than surface a 500 for
            # something as recoverable as "the rubric wasn't customized this time".
            return RubricOutput(criteria=[RubricCriterionOut(**c) for c in default], source="default")

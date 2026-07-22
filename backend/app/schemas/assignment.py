"""Request/response models for assignment templates, assignments, rubrics,
and test cases."""
import uuid

from pydantic import BaseModel, Field

from app.db.models.assignment import AssignmentType, TestCaseKind


class AssignmentTemplateOut(BaseModel):
    id: uuid.UUID
    name: str
    assignment_type: AssignmentType
    default_fields: dict

    model_config = {"from_attributes": True}


class RubricCriterion(BaseModel):
    name: str
    weight: float = Field(gt=0, le=1)


class RubricOut(BaseModel):
    criteria: list[RubricCriterion]

    model_config = {"from_attributes": True}


class AssignmentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    type: AssignmentType = AssignmentType.programming
    template_id: uuid.UUID | None = None
    difficulty: str | None = None
    constraints: dict = Field(default_factory=dict)
    timeout_seconds: int = Field(default=5, ge=1, le=60)
    # Only meaningful for type=programming; used to seed the reference-solution-driven
    # AssignmentSetupAgent flow. Optional here — a teacher can also add test cases
    # manually via the test-cases endpoints below.
    reference_solution: str | None = None
    functions: list[dict] = Field(default_factory=list)  # [{"name": ..., "signature": ...}]


class AssignmentUpdate(BaseModel):
    """Partial update — every field optional, only supplied ones change. Added
    primarily so a dedicated MCQ editor can save questions after the assignment
    already exists (previously there was no way to change `constraints` post-
    creation at all)."""
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    difficulty: str | None = None
    constraints: dict | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=60)


class AssignmentOut(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    template_id: uuid.UUID | None
    type: AssignmentType
    title: str
    description: str
    difficulty: str | None
    constraints: dict
    timeout_seconds: int
    rubric: RubricOut | None = None

    model_config = {"from_attributes": True}


class TestCaseCreate(BaseModel):
    kind: TestCaseKind = TestCaseKind.public
    input: dict
    expected_output: dict
    points: int = Field(default=1, ge=1)


class TestCaseOut(BaseModel):
    id: uuid.UUID
    kind: TestCaseKind
    input: dict
    expected_output: dict
    points: int

    model_config = {"from_attributes": True}


class GenerateTestCasesRequest(BaseModel):
    """Drives the ported AssignmentSetupAgent — see agents/assignment_setup_agent.py.
    Requires an LLM provider configured (GEMINI_API_KEY/GROQ_API_KEY); raises 400
    otherwise, same as the agent's own behavior."""
    reference_solution: str
    functions: list[dict]  # [{"name": ..., "signature": ...}]
    language: str = "python"  # "python" or "java" — must match the assignment's grading language

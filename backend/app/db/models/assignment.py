"""
Assignment-authoring tables: templates, assignments themselves, rubrics
(criteria are stored as JSON — see Rubric Agent in agents/), and test cases.

The rubric IS still allowed to be lightweight for programming assignments
(each test case carries its own `points`, same as the original prototype),
but Rubric now also exists as its own row so non-programming types
(Theory, Design, Case Study) — which have no test cases at all — still get
a real, gradable rubric.
"""
import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class AssignmentType(str, enum.Enum):
    programming = "programming"
    sql = "sql"
    theory = "theory"
    mcq = "mcq"
    case_study = "case_study"
    design = "design"


class TestCaseKind(str, enum.Enum):
    public = "public"
    hidden = "hidden"
    edge = "edge"


class AssignmentTemplate(UUIDPKMixin, Base):
    __tablename__ = "assignment_templates"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    assignment_type: Mapped[AssignmentType] = mapped_column(Enum(AssignmentType, name="assignment_type"))
    # Required fields + default rubric/evaluation-strategy hints for this template,
    # consumed by the Assignment Agent when a teacher picks this template.
    default_fields: Mapped[dict] = mapped_column(JSONB, default=dict)


class Assignment(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "assignments"

    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("courses.id"))
    template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("assignment_templates.id"))
    type: Mapped[AssignmentType] = mapped_column(Enum(AssignmentType, name="assignment_type"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    difficulty: Mapped[str | None] = mapped_column(String(50))
    constraints: Mapped[dict] = mapped_column(JSONB, default=dict)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=5)

    course: Mapped["Course"] = relationship(back_populates="assignments")
    rubric: Mapped["Rubric"] = relationship(back_populates="assignment", uselist=False, cascade="all, delete-orphan")
    test_cases: Mapped[list["TestCase"]] = relationship(back_populates="assignment", cascade="all, delete-orphan")
    submissions: Mapped[list["Submission"]] = relationship(back_populates="assignment")


class Rubric(UUIDPKMixin, Base):
    __tablename__ = "rubrics"

    assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assignments.id"), unique=True)
    # [{"name": "correctness", "weight": 0.5}, {"name": "readability", "weight": 0.1}, ...]
    criteria: Mapped[list] = mapped_column(JSONB, default=list)

    assignment: Mapped["Assignment"] = relationship(back_populates="rubric")


class TestCase(UUIDPKMixin, Base):
    __tablename__ = "test_cases"

    assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assignments.id"))
    kind: Mapped[TestCaseKind] = mapped_column(Enum(TestCaseKind, name="test_case_kind"))
    input: Mapped[dict] = mapped_column(JSONB)
    expected_output: Mapped[dict] = mapped_column(JSONB)
    points: Mapped[int] = mapped_column(Integer, default=1)

    assignment: Mapped["Assignment"] = relationship(back_populates="test_cases")

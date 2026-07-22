"""
Grading-pipeline tables: a submission and its 1:1 execution result and
feedback (one attempt = one row each — resubmission creates new rows,
giving a full history rather than overwriting, unlike the original
prototype's overwrite-on-rerun JSON files), plus pairwise similarity reports.
"""
import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class Submission(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "submissions"

    assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assignments.id"))
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("students.id"))
    language: Mapped[str | None] = mapped_column(String(50))  # python|java|cpp|javascript|null for non-code types
    content: Mapped[str] = mapped_column(Text)

    assignment: Mapped["Assignment"] = relationship(back_populates="submissions")
    execution_result: Mapped["ExecutionResult"] = relationship(
        back_populates="submission", uselist=False, cascade="all, delete-orphan"
    )
    feedback: Mapped["Feedback"] = relationship(
        back_populates="submission", uselist=False, cascade="all, delete-orphan"
    )


class ExecutionResult(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "execution_results"

    submission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("submissions.id"), unique=True)
    status: Mapped[str] = mapped_column(String(30))  # ok|timeout|crash|rejected
    raw_output: Mapped[dict] = mapped_column(JSONB, default=dict)
    runtime_ms: Mapped[float | None] = mapped_column(Float)

    submission: Mapped["Submission"] = relationship(back_populates="execution_result")


class Feedback(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "feedback"

    submission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("submissions.id"), unique=True)
    score: Mapped[float] = mapped_column(Float, default=0)
    total_points: Mapped[float] = mapped_column(Float, default=0)
    breakdown: Mapped[list] = mapped_column(JSONB, default=list)
    strengths: Mapped[str | None] = mapped_column(Text)
    weaknesses: Mapped[str | None] = mapped_column(Text)
    hints: Mapped[list] = mapped_column(JSONB, default=list)

    submission: Mapped["Submission"] = relationship(back_populates="feedback")


class SimilarityReport(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "similarity_reports"

    assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assignments.id"))
    submission_a_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("submissions.id"))
    submission_b_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("submissions.id"))
    technique: Mapped[str] = mapped_column(String(30))  # ast|token|embedding
    score: Mapped[float] = mapped_column(Float)

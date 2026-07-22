"""
Analytics — business logic behind api/v1/analytics.py.

Computed on-demand and persisted into AnalyticsSnapshot (a "refresh"
action a teacher/admin explicitly triggers) rather than recomputed on
every dashboard load — per the AnalyticsSnapshot model's own docstring
from Phase 0. GET routes read the latest snapshot; if none exists yet,
that's a 404 telling the caller to POST .../refresh first, not a silent
empty response that looks like "zero submissions" when it actually means
"never computed."
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.analytics_agent import (
    AssignmentAnalyticsAgent, AssignmentAnalyticsInput, AssignmentPerformanceSummary,
    CourseAnalyticsAgent, CourseAnalyticsInput, SubmissionSummary,
)
from app.db.models.academic import Course
from app.db.models.analytics import AnalyticsSnapshot
from app.db.models.assignment import Assignment, TestCase
from app.db.models.submission import ExecutionResult, Feedback, SimilarityReport, Submission

_assignment_analytics = AssignmentAnalyticsAgent()
_course_analytics = CourseAnalyticsAgent()


class NotFoundError(Exception):
    pass


class OwnershipError(Exception):
    pass


async def _ensure_course_access(
    db: AsyncSession, course_id: uuid.UUID, teacher_id: uuid.UUID | None, is_admin: bool,
) -> Course:
    """Admins can access any course's analytics; teachers only their own — explicit
    is_admin flag rather than overloading teacher_id=None to mean two different
    things (that ambiguity is exactly the kind of authorization bug worth avoiding)."""
    course = await db.get(Course, course_id)
    if course is None:
        raise NotFoundError("Course not found.")
    if is_admin:
        return course
    if teacher_id is None or course.teacher_id != teacher_id:
        raise OwnershipError("You do not own this course.")
    return course


async def _category_by_test_case_id(db: AsyncSession, assignment_id: uuid.UUID) -> dict[str, str]:
    result = await db.execute(select(TestCase).where(TestCase.assignment_id == assignment_id))
    return {str(tc.id): (tc.input.get("category") or "general") for tc in result.scalars().all()}


async def compute_assignment_analytics(
    db: AsyncSession, assignment_id: uuid.UUID, teacher_id: uuid.UUID | None, is_admin: bool = False,
) -> AnalyticsSnapshot:
    assignment = await db.get(Assignment, assignment_id)
    if assignment is None:
        raise NotFoundError("Assignment not found.")
    await _ensure_course_access(db, assignment.course_id, teacher_id, is_admin)

    result = await db.execute(
        select(Submission, Feedback, ExecutionResult)
        .join(Feedback, Feedback.submission_id == Submission.id)
        .outerjoin(ExecutionResult, ExecutionResult.submission_id == Submission.id)
        .where(Submission.assignment_id == assignment_id)
    )
    rows = result.all()

    category_by_tc_id = await _category_by_test_case_id(db, assignment_id)

    summaries = []
    for submission, feedback, execution_result in rows:
        failing_categories = []
        if execution_result is not None:
            for r in execution_result.raw_output.get("results", []):
                if not r.get("passed", True):
                    failing_categories.append(r.get("category") or category_by_tc_id.get(r.get("id"), "general"))
        summaries.append(SubmissionSummary(
            student_id=str(submission.student_id), score=feedback.score, total_points=feedback.total_points,
            exec_status=execution_result.status if execution_result else "n/a",
            failing_categories=failing_categories,
        ))

    plagiarism_rows = (await db.execute(
        select(SimilarityReport).where(SimilarityReport.assignment_id == assignment_id)
    )).scalars().all()

    output = _assignment_analytics.run(AssignmentAnalyticsInput(
        assignment_title=assignment.title, submissions=summaries,
        plagiarism_flagged_pair_count=len(plagiarism_rows),
    ))

    snapshot = AnalyticsSnapshot(scope="assignment", scope_id=assignment_id, metrics=output.model_dump())
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot


async def compute_course_analytics(
    db: AsyncSession, course_id: uuid.UUID, teacher_id: uuid.UUID | None, is_admin: bool = False,
) -> AnalyticsSnapshot:
    course = await _ensure_course_access(db, course_id, teacher_id, is_admin)

    result = await db.execute(select(Assignment).where(Assignment.course_id == course_id))
    assignments = list(result.scalars().all())

    assignment_summaries = []
    total_plagiarism = 0
    for assignment in assignments:
        # Reuses the assignment-level computation (and writes its own snapshot row
        # along the way — a course refresh transitively refreshes every assignment
        # it contains, which is the intended behavior: a course-level dashboard load
        # asks "how's the course doing right now," not "how was it doing as of
        # whenever each assignment was last individually refreshed").
        snap = await compute_assignment_analytics(db, assignment.id, teacher_id, is_admin)
        metrics = snap.metrics
        assignment_summaries.append(AssignmentPerformanceSummary(
            assignment_id=str(assignment.id), title=assignment.title,
            average_score_pct=metrics.get("average_score_pct"), submission_count=metrics.get("submission_count", 0),
        ))
        total_plagiarism += metrics.get("plagiarism_flagged_pair_count", 0)

    output = _course_analytics.run(CourseAnalyticsInput(
        course_name=course.name, assignment_summaries=assignment_summaries,
        total_plagiarism_flagged_pair_count=total_plagiarism,
    ))

    snapshot = AnalyticsSnapshot(scope="course", scope_id=course_id, metrics=output.model_dump())
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot


async def _get_latest_snapshot(db: AsyncSession, scope: str, scope_id: uuid.UUID) -> AnalyticsSnapshot:
    result = await db.execute(
        select(AnalyticsSnapshot)
        .where(AnalyticsSnapshot.scope == scope, AnalyticsSnapshot.scope_id == scope_id)
        .order_by(AnalyticsSnapshot.generated_at.desc())
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()
    if snapshot is None:
        raise NotFoundError(
            f"No analytics computed yet for this {scope} — POST the /analytics/refresh endpoint first."
        )
    return snapshot


async def get_latest_assignment_analytics(
    db: AsyncSession, assignment_id: uuid.UUID, teacher_id: uuid.UUID | None, is_admin: bool = False,
) -> AnalyticsSnapshot:
    assignment = await db.get(Assignment, assignment_id)
    if assignment is None:
        raise NotFoundError("Assignment not found.")
    await _ensure_course_access(db, assignment.course_id, teacher_id, is_admin)
    return await _get_latest_snapshot(db, "assignment", assignment_id)


async def get_latest_course_analytics(
    db: AsyncSession, course_id: uuid.UUID, teacher_id: uuid.UUID | None, is_admin: bool = False,
) -> AnalyticsSnapshot:
    await _ensure_course_access(db, course_id, teacher_id, is_admin)
    return await _get_latest_snapshot(db, "course", course_id)

"""
Assignments, rubrics, and test cases — business logic behind
api/v1/assignments.py. Every mutating operation checks that the acting
teacher actually owns the assignment's course (`_ensure_owner`) — this is
the ownership check the architecture doc's RBAC design calls for beyond
plain role membership.

No course-enrollment table exists yet in the schema (the original spec
didn't call for one and it wasn't in the Phase 0 design), so for now any
authenticated student can view/submit to any assignment. Worth revisiting
if a real "my enrolled courses" view is ever needed — flagging it here
rather than silently working around it.
"""
import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.assignment_setup_agent import (
    AssignmentSetupAgent, AssignmentSetupInput, FunctionSpec,
)
from app.agents.rubric_agent import RubricAgent, RubricInput
from app.db.models.academic import Course, Subject
from app.db.models.assignment import (
    Assignment, AssignmentType, Rubric, TestCase, TestCaseKind,
)


class NotFoundError(Exception):
    pass


class OwnershipError(Exception):
    pass


_agent = AssignmentSetupAgent()
_rubric_agent = RubricAgent()


async def _ensure_owner(db: AsyncSession, course_id: uuid.UUID, teacher_id: uuid.UUID) -> Course:
    course = await db.get(Course, course_id)
    if course is None:
        raise NotFoundError("Course not found.")
    if course.teacher_id != teacher_id:
        raise OwnershipError("You do not own this course.")
    return course


async def create_assignment(
    db: AsyncSession, course_id: uuid.UUID, teacher_id: uuid.UUID,
    title: str, description: str, type_: AssignmentType, template_id: uuid.UUID | None,
    difficulty: str | None, constraints: dict, timeout_seconds: int,
) -> Assignment:
    course = await _ensure_owner(db, course_id, teacher_id)

    assignment = Assignment(
        course_id=course_id, template_id=template_id, type=type_, title=title,
        description=description, difficulty=difficulty, constraints=constraints,
        timeout_seconds=timeout_seconds,
    )
    db.add(assignment)
    await db.flush()

    subject = await db.get(Subject, course.subject_id)
    rubric_result = _rubric_agent.run(RubricInput(
        title=title, description=description, assignment_type=type_,
        subject_name=subject.name if subject else None,
    ))
    db.add(Rubric(
        assignment_id=assignment.id,
        criteria=[c.model_dump() for c in rubric_result.criteria],
    ))

    await db.commit()
    return await get_assignment(db, assignment.id)


async def update_assignment(
    db: AsyncSession, assignment_id: uuid.UUID, teacher_id: uuid.UUID, updates: dict,
) -> Assignment:
    """Partial update, e.g. the MCQ editor saving `constraints={"questions": [...]}`
    after the assignment was created without any questions yet. `updates` should
    already have unset fields stripped (see the route's `exclude_unset=True`)."""
    assignment = await get_assignment(db, assignment_id)
    await _ensure_owner(db, assignment.course_id, teacher_id)

    for field, value in updates.items():
        setattr(assignment, field, value)
    await db.commit()
    return await get_assignment(db, assignment_id)


async def regenerate_rubric(db: AsyncSession, assignment_id: uuid.UUID, teacher_id: uuid.UUID) -> Rubric:
    """Re-runs the Rubric Agent for an existing assignment and overwrites its rubric —
    e.g. after a teacher edits the description enough that the original criteria no
    longer fit. Kept as an explicit, separate action rather than auto-triggered on
    every description edit, since silently rewriting grading weights on a save the
    teacher didn't realize would do that is exactly the kind of "helpful" surprise
    that erodes trust in an autonomous system."""
    assignment = await get_assignment(db, assignment_id)
    course = await _ensure_owner(db, assignment.course_id, teacher_id)

    subject = await db.get(Subject, course.subject_id)
    rubric_result = _rubric_agent.run(RubricInput(
        title=assignment.title, description=assignment.description, assignment_type=assignment.type,
        subject_name=subject.name if subject else None,
    ))

    result = await db.execute(select(Rubric).where(Rubric.assignment_id == assignment_id))
    rubric = result.scalar_one_or_none()
    if rubric is None:
        rubric = Rubric(assignment_id=assignment_id, criteria=[])
        db.add(rubric)
    rubric.criteria = [c.model_dump() for c in rubric_result.criteria]

    await db.commit()
    await db.refresh(rubric)
    return rubric


async def get_assignment(db: AsyncSession, assignment_id: uuid.UUID) -> Assignment:
    result = await db.execute(
        select(Assignment).where(Assignment.id == assignment_id).options(selectinload(Assignment.rubric))
    )
    assignment = result.scalar_one_or_none()
    if assignment is None:
        raise NotFoundError("Assignment not found.")
    return assignment


async def list_assignments(db: AsyncSession, course_id: uuid.UUID) -> list[Assignment]:
    result = await db.execute(
        select(Assignment).where(Assignment.course_id == course_id).options(selectinload(Assignment.rubric))
    )
    return list(result.scalars().all())


async def add_test_case(
    db: AsyncSession, assignment_id: uuid.UUID, teacher_id: uuid.UUID,
    kind: TestCaseKind, input_: dict, expected_output: dict, points: int,
) -> TestCase:
    assignment = await get_assignment(db, assignment_id)
    await _ensure_owner(db, assignment.course_id, teacher_id)

    test_case = TestCase(
        assignment_id=assignment_id, kind=kind, input=input_, expected_output=expected_output, points=points,
    )
    db.add(test_case)
    await db.commit()
    await db.refresh(test_case)
    return test_case


async def list_test_cases(db: AsyncSession, assignment_id: uuid.UUID, include_hidden: bool) -> list[TestCase]:
    stmt = select(TestCase).where(TestCase.assignment_id == assignment_id)
    if not include_hidden:
        stmt = stmt.where(TestCase.kind == TestCaseKind.public)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def generate_test_cases(
    db: AsyncSession, assignment_id: uuid.UUID, teacher_id: uuid.UUID,
    reference_solution: str, functions: list[dict], language: str = "python",
) -> list[TestCase]:
    """Runs the ported AssignmentSetupAgent (LLM-proposed, execution-verified against
    the reference solution — see agents/assignment_setup_agent.py) and persists the
    result as TestCase rows. Raises ValueError (-> 400 at the route) if no LLM
    provider is configured or generation/verification fails, exactly matching the
    agent's own contract.

    Runs the agent via asyncio.to_thread: it makes a blocking LLM HTTP call and then
    shells out to a subprocess (Python) or javac+java (Java) to verify the proposed
    test cases, all synchronous. Even though that subprocess work is itself now
    timeout-bounded (see assignment_setup_agent.py), calling it directly from this
    async route would still block the whole event loop — every other request on this
    worker — for however long that takes. to_thread keeps a slow/misbehaving
    generation from starving unrelated requests."""
    assignment = await get_assignment(db, assignment_id)
    await _ensure_owner(db, assignment.course_id, teacher_id)

    output = await asyncio.to_thread(_agent.run, AssignmentSetupInput(
        title=assignment.title,
        description=assignment.description,
        functions=[FunctionSpec(**f) for f in functions],
        reference_source=reference_solution,
        language=language,
    ))

    created = []
    for tc in output.test_cases:
        kind = TestCaseKind.hidden if len(created) % 3 != 0 else TestCaseKind.public  # ~1/3 public, rest hidden
        row = TestCase(
            assignment_id=assignment_id,
            kind=kind,
            input={"function": tc["function"], "args": tc.get("args", [])},
            expected_output=(
                {"expect_raises": tc["expect_raises"]} if "expect_raises" in tc else {"value": tc.get("expected")}
            ),
            points=tc.get("points", 1),
        )
        db.add(row)
        created.append(row)

    await db.commit()
    for row in created:
        await db.refresh(row)
    return created

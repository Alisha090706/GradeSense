"""
Tutor conversations — business logic behind api/v1/tutor.py. Fetches the
raw context (recent messages, submission execution/feedback, past
submission outcomes for recurring-mistake detection, RAG chunks if the
course has ingested documents) and hands it to MemoryAgent then
TutorAgent — both DB-agnostic, same pattern as every other agent.

A "conversation thread" is implicitly all TutorMessage rows for a given
(student_id, submission_id) pair — submission_id nullable for general,
not-tied-to-one-submission questions. No separate conversation/thread
table; the messages themselves ARE the thread, per the architecture doc's
"long-term memory = Postgres tables, not a separate store" design.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.memory_agent import MemoryAgent, MemoryInput, PastSubmissionOutcome
from app.agents.retrieval_agent import RetrieveInput, retrieve
from app.agents.tutor_agent import ExecutionContext, RetrievedContext, TutorAgent, TutorInput
from app.db.models.assignment import Assignment
from app.db.models.conversation import MessageRole, TutorMessage
from app.db.models.submission import ExecutionResult, Feedback, Submission

_memory = MemoryAgent()
_tutor = TutorAgent()

RECENT_MESSAGE_LIMIT = 10


class NotFoundError(Exception):
    pass


class OwnershipError(Exception):
    pass


async def _recent_messages(db: AsyncSession, student_id: uuid.UUID, submission_id: uuid.UUID | None) -> list[dict]:
    stmt = select(TutorMessage).where(TutorMessage.student_id == student_id)
    stmt = stmt.where(TutorMessage.submission_id == submission_id) if submission_id else stmt.where(TutorMessage.submission_id.is_(None))
    stmt = stmt.order_by(TutorMessage.created_at.desc()).limit(RECENT_MESSAGE_LIMIT)
    result = await db.execute(stmt)
    rows = list(reversed(result.scalars().all()))  # oldest first for the agent
    return [{"role": r.role.value, "content": r.content} for r in rows]


async def _past_submission_outcomes(
    db: AsyncSession, student_id: uuid.UUID, course_id: uuid.UUID, exclude_submission_id: uuid.UUID | None,
) -> list[PastSubmissionOutcome]:
    result = await db.execute(
        select(Submission, Assignment, ExecutionResult)
        .join(Assignment, Assignment.id == Submission.assignment_id)
        .outerjoin(ExecutionResult, ExecutionResult.submission_id == Submission.id)
        .where(Submission.student_id == student_id, Assignment.course_id == course_id)
    )
    outcomes = []
    for submission, assignment, execution_result in result.all():
        if submission.id == exclude_submission_id:
            continue
        failing = []
        if execution_result:
            for r in execution_result.raw_output.get("results", []):
                if not r.get("passed", True):
                    failing.append(r.get("category", "general"))
        outcomes.append(PastSubmissionOutcome(assignment_title=assignment.title, failing_categories=failing))
    return outcomes


async def ask(
    db: AsyncSession, student_id: uuid.UUID, question: str, submission_id: uuid.UUID | None,
) -> dict:
    submission_context = None
    assignment_description = ""
    course_id = None

    if submission_id is not None:
        submission = await db.get(Submission, submission_id)
        if submission is None:
            raise NotFoundError("Submission not found.")
        if submission.student_id != student_id:
            raise OwnershipError("This isn't your submission.")

        assignment = await db.get(Assignment, submission.assignment_id)
        assignment_description = assignment.description
        course_id = assignment.course_id

        feedback_result = await db.execute(select(Feedback).where(Feedback.submission_id == submission_id))
        feedback = feedback_result.scalar_one_or_none()
        exec_result_row = await db.execute(select(ExecutionResult).where(ExecutionResult.submission_id == submission_id))
        execution_result = exec_result_row.scalar_one_or_none()

        if execution_result is not None:
            failing_tests = [r for r in execution_result.raw_output.get("results", []) if not r.get("passed", True)]
            submission_context = ExecutionContext(
                exec_status=execution_result.status, failing_tests=failing_tests,
                score=feedback.score if feedback else None, total_points=feedback.total_points if feedback else None,
            )

    recent = await _recent_messages(db, student_id, submission_id)

    recurring_mistakes = []
    if course_id is not None:
        past_outcomes = await _past_submission_outcomes(db, student_id, course_id, submission_id)
        memory_result = _memory.run(MemoryInput(recent_messages=recent, past_submissions=past_outcomes))
        recurring_mistakes = [m.category for m in memory_result.recurring_mistakes]

    retrieved_chunks = []
    used_rag_search = False
    if course_id is not None:
        retrieval_result = retrieve(RetrieveInput(course_id=str(course_id), query=question, top_k=3))
        used_rag_search = retrieval_result.available
        retrieved_chunks = [RetrievedContext(text=c.text, filename=c.filename) for c in retrieval_result.chunks]

    tutor_result = _tutor.run(TutorInput(
        student_question=question, assignment_description=assignment_description,
        submission_context=submission_context, retrieved_chunks=retrieved_chunks,
        recent_messages=recent, recurring_mistake_categories=recurring_mistakes,
    ))

    db.add(TutorMessage(student_id=student_id, submission_id=submission_id, role=MessageRole.user, content=question))
    db.add(TutorMessage(
        student_id=student_id, submission_id=submission_id, role=MessageRole.tutor, content=tutor_result.answer,
    ))
    await db.commit()

    return {
        "answer": tutor_result.answer,
        "used_llm": tutor_result.used_llm,
        "used_rag": tutor_result.used_rag,
        "rag_search_available": used_rag_search,
        "recurring_mistakes": recurring_mistakes,
    }


async def get_history(db: AsyncSession, student_id: uuid.UUID, submission_id: uuid.UUID | None) -> list[TutorMessage]:
    stmt = select(TutorMessage).where(TutorMessage.student_id == student_id)
    stmt = stmt.where(TutorMessage.submission_id == submission_id) if submission_id else stmt.where(TutorMessage.submission_id.is_(None))
    result = await db.execute(stmt.order_by(TutorMessage.created_at.asc()))
    return list(result.scalars().all())

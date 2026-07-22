"""
Submission creation and grading — the DB-backed consumer of OrchestratorV2
(agents/orchestrator_v2.py). Loads DB rows into the orchestrator's plain
in-memory context (assembling type-specific inputs into ctx.extra per
assignment type — see _build_context), runs the decision-table pipeline,
and persists from the pipeline's normalized final_* fields uniformly
regardless of which branch actually ran.

Known gap, flagged rather than silently worked around: rubric criteria
are only consulted for scoring on the Theory branch so far (where there's
nothing else to score against) — Programming and SQL still score purely
off test-case points, same as the original prototype. Fully rubric-
weighted scoring across every type is natural follow-up work, not done
here to avoid changing Programming's scoring behavior in the same phase
that widened evaluation to new types.
"""
import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.evaluation.schemas import SUPPORTED_LANGUAGES
from app.agents.orchestrator_v2 import OrchestratorV2, PeerSubmission, PipelineContext
from app.db.models.assignment import Assignment, AssignmentType, Rubric, TestCase
from app.db.models.submission import ExecutionResult, Feedback, SimilarityReport, Submission
from app.services.assignment_service import get_assignment, list_test_cases

_orchestrator = OrchestratorV2()


class NotFoundError(Exception):
    pass


def _to_legacy_test_case(tc: TestCase) -> dict:
    """Adapts a DB TestCase row to the flat dict shape python_harness.py / the
    LanguageRunners expect — see agents/evaluation/harnesses/python_harness.py's
    docstring for the authoritative schema. Programming assignments only."""
    d = {
        "id": str(tc.id),
        "category": tc.input.get("category") or tc.input.get("function", "general"),
        "function": tc.input.get("function"),
        "args": tc.input.get("args", []),
        "points": tc.points,
    }
    if "expect_raises" in tc.expected_output:
        d["expect_raises"] = tc.expected_output["expect_raises"]
    else:
        d["expected"] = tc.expected_output.get("value")
    return d


def _to_sql_test_case(tc: TestCase) -> dict:
    """Adapts a DB TestCase row into sql_evaluation_agent.SqlTestCase's shape.
    expected_output is expected to hold {"rows": [[...], ...]}."""
    return {
        "id": str(tc.id),
        "category": tc.input.get("category", "query_correctness"),
        "expected_rows": tc.expected_output.get("rows", []),
        "points": tc.points,
        "seed_sql_override": tc.input.get("seed_sql_override"),
    }


async def _latest_peer_submissions(db: AsyncSession, assignment_id: uuid.UUID, exclude_student_id: uuid.UUID):
    result = await db.execute(
        select(Submission)
        .where(Submission.assignment_id == assignment_id, Submission.student_id != exclude_student_id)
        .order_by(Submission.created_at.desc())
    )
    seen: set[uuid.UUID] = set()
    peers: list[Submission] = []
    for row in result.scalars().all():
        if row.student_id in seen:
            continue
        seen.add(row.student_id)
        peers.append(row)
    return peers


async def _build_context(
    db: AsyncSession, assignment: Assignment, student_id: uuid.UUID, content: str, language: str,
    peer_rows: list[Submission],
) -> PipelineContext:
    """Assembles the per-type ctx.extra payload the orchestrator's SQL/MCQ/Theory
    branches read from — see orchestrator_v2.py's step functions for what each
    key is used for."""
    base_kwargs = dict(
        assignment_type=assignment.type,
        student_id=str(student_id),
        submission_content=content,
        # For Programming, this is the real submitted language (python/java/cpp/
        # javascript) and drives runner dispatch + feedback wording. For every
        # other type it's not a real "language" in that sense, but SQL's shared
        # _step_feedback still reads it for wording, so it gets a type-appropriate
        # label here rather than carrying over whatever the client happened to send.
        language=language if assignment.type == AssignmentType.programming else assignment.type.value,
        assignment_description=assignment.description,
        timeout_seconds=assignment.timeout_seconds,
        peer_submissions=[PeerSubmission(student_id=str(p.student_id), content=p.content) for p in peer_rows],
    )

    if assignment.type == AssignmentType.programming:
        test_case_rows = await list_test_cases(db, assignment.id, include_hidden=True)
        if not test_case_rows:
            raise ValueError("This assignment has no test cases yet — nothing to grade against.")
        return PipelineContext(
            test_cases=[_to_legacy_test_case(tc) for tc in test_case_rows], **base_kwargs,
        )

    if assignment.type == AssignmentType.sql:
        test_case_rows = await list_test_cases(db, assignment.id, include_hidden=True)
        if not test_case_rows:
            raise ValueError("This assignment has no test cases yet — nothing to grade against.")
        if "schema_sql" not in assignment.constraints:
            raise ValueError("This SQL assignment is missing schema_sql in its constraints — ask the teacher to set it up.")
        sql_test_cases = [_to_sql_test_case(tc) for tc in test_case_rows]
        return PipelineContext(
            # Shared with the SQL evaluator's own input AND with FeedbackAgent's
            # scoring (which only reads id/category/points off each dict — the
            # extra expected_rows/seed_sql_override keys are harmless there).
            test_cases=sql_test_cases,
            extra={
                "schema_sql": assignment.constraints["schema_sql"],
                "seed_sql": assignment.constraints.get("seed_sql", ""),
                "order_matters": assignment.constraints.get("order_matters", False),
                "sql_test_cases": sql_test_cases,
            },
            **base_kwargs,
        )

    if assignment.type == AssignmentType.mcq:
        questions = assignment.constraints.get("questions")
        if not questions:
            raise ValueError("This MCQ assignment has no questions configured — ask the teacher to add some.")

        try:
            selections = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            raise ValueError("MCQ submissions must be a JSON object mapping question id to a list of selected "
                              "option keys, e.g. {\"q1\": [\"B\"]}.")
        if not isinstance(selections, dict):
            raise ValueError("MCQ submission content must be a JSON object keyed by question id.")

        answers = []
        for q in questions:
            qid = q["id"]
            selected = selections.get(qid, [])
            if isinstance(selected, str):
                selected = [selected]  # tolerate a bare string for a single-answer question
            if not isinstance(selected, list) or not all(isinstance(s, str) for s in selected):
                raise ValueError(f"Selection for question '{qid}' must be a list of option-key strings.")
            answers.append({
                "question_id": qid,
                "question_text": q.get("text", ""),
                "selected": selected,
                "correct": q.get("correct_options", []),
                "points": q.get("points", 1),
            })
        return PipelineContext(
            test_cases=[],
            extra={"answers": answers},
            **base_kwargs,
        )

    if assignment.type == AssignmentType.theory:
        result = await db.execute(select(Rubric).where(Rubric.assignment_id == assignment.id))
        rubric = result.scalar_one_or_none()
        criteria = rubric.criteria if rubric else [{"name": "overall_quality", "weight": 1.0}]
        return PipelineContext(test_cases=[], extra={"rubric_criteria": criteria}, **base_kwargs)

    raise ValueError(
        f"Assignment type '{assignment.type.value}' isn't gradeable yet — case_study and design "
        f"pipelines are a Phase 6+ follow-up."
    )


async def create_submission(
    db: AsyncSession, assignment_id: uuid.UUID, student_id: uuid.UUID, content: str, language: str,
) -> dict:
    assignment: Assignment = await get_assignment(db, assignment_id)

    # Language only means anything for Programming submissions — the DB model's own
    # docstring says as much ("python|java|cpp|javascript|null for non-code types").
    # Validating it against SUPPORTED_LANGUAGES for SQL/MCQ/Theory would incorrectly
    # reject every one of them, since "sql"/"mcq"/"theory" aren't in that set and
    # forcing a student to claim language="python" for a SQL query makes no sense.
    if assignment.type == AssignmentType.programming:
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language '{language}'. Supported: {sorted(SUPPORTED_LANGUAGES)}.")
        stored_language = language
    else:
        stored_language = None

    peer_rows = await _latest_peer_submissions(db, assignment_id, student_id)
    ctx = await _build_context(db, assignment, student_id, content, language, peer_rows)
    ctx = _orchestrator.run(ctx)

    submission = Submission(
        assignment_id=assignment_id, student_id=student_id, language=stored_language, content=content,
    )
    db.add(submission)
    await db.flush()

    if ctx.exec_result is not None:
        db.add(ExecutionResult(
            submission_id=submission.id,
            status=ctx.exec_result.status,
            raw_output={"results": ctx.exec_result.results, "raw_error": ctx.exec_result.raw_error},
            runtime_ms=ctx.exec_result.elapsed_ms,
        ))

    db.add(Feedback(
        submission_id=submission.id,
        score=ctx.final_score,
        total_points=ctx.final_total_points,
        breakdown=ctx.final_breakdown,
        # Every evaluation branch still produces one undifferentiated feedback
        # string rather than a true strengths/weaknesses split — stored here
        # rather than force-splitting it. hints stays empty until the
        # progressive hint-ladder described in the architecture doc exists.
        strengths=ctx.final_feedback_text,
        weaknesses=None,
        hints=[],
    ))

    similarity_flagged = []
    if ctx.similarity_findings:
        peer_submission_by_student = {str(p.student_id): p.id for p in peer_rows}
        for finding in ctx.similarity_findings:
            other_id = finding.student_b if finding.student_a == str(student_id) else finding.student_a
            other_submission_id = peer_submission_by_student.get(other_id)
            if other_submission_id is None:
                continue
            db.add(SimilarityReport(
                assignment_id=assignment_id,
                submission_a_id=submission.id,
                submission_b_id=other_submission_id,
                technique=finding.technique,
                score=finding.similarity,
            ))
            similarity_flagged.append({
                "peer_student_id": other_id, "similarity": finding.similarity, "technique": finding.technique,
            })

    await db.commit()

    return {
        "submission_id": submission.id,
        "exec_status": ctx.final_status,
        "score": ctx.final_score,
        "total_points": ctx.final_total_points,
        "breakdown": ctx.final_breakdown,
        "feedback": ctx.final_feedback_text,
        "failing_tests": ctx.final_failing_tests,
        "similarity_flagged": similarity_flagged,
        "pipeline_log": ctx.log,
    }


async def get_submission_detail(db: AsyncSession, submission_id: uuid.UUID) -> Submission:
    result = await db.execute(select(Submission).where(Submission.id == submission_id))
    submission = result.scalar_one_or_none()
    if submission is None:
        raise NotFoundError("Submission not found.")
    return submission


async def list_my_submissions(db: AsyncSession, assignment_id: uuid.UUID, student_id: uuid.UUID) -> list[Submission]:
    result = await db.execute(
        select(Submission)
        .where(Submission.assignment_id == assignment_id, Submission.student_id == student_id)
        .order_by(Submission.created_at.desc())
    )
    return list(result.scalars().all())

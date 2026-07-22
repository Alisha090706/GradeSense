"""
Orchestrator v2 — Phase 4, widened in Phase 6 (SQL/Theory/MCQ) and
Phase 7 (multi-technique Similarity).

An explicit decision-table state machine, per the architecture doc's §2.3
design: a small pipeline graph per assignment type
(PIPELINE_GRAPH[AssignmentType]), where each step declares its own
skip_if condition instead of the whole pipeline being one fixed sequence.

Phase 7 splits the old single "similarity" step into three —
similarity_ast, similarity_token, similarity_embedding — each with its
own skip condition and each reporting under its own `technique` value
rather than one collapsed score (see agents/token_similarity_agent.py
and embedding_similarity_agent.py for why). AST stays Python-only; token
and embedding are plain-text techniques that run for every language,
which is what finally makes similarity checking possible for the Java/
C++/JS submissions Phase 5 introduced.

Every branch converges on the same normalized `final_*` fields on
PipelineContext (final_status, final_score, final_total_points,
final_breakdown, final_feedback_text, final_failing_tests) and, for
similarity, a flat `similarity_findings` list tagged by technique —
submission_service.py persists from both uniformly rather than needing
type- or technique-specific persistence branches of its own.

Deliberately DB-agnostic: takes plain in-memory inputs, returns plain
in-memory outputs. submission_service.py owns loading DB rows in and
persisting agent outputs back out.
"""
import ast
import os
import tempfile
from dataclasses import dataclass, field
from typing import Callable

from app.agents.execution_agent import ExecutionAgent, ExecutionInput, ExecutionOutput
from app.agents.embedding_similarity_agent import EmbeddingSimilarityAgent, EmbeddingCandidate, EmbeddingSimilarityInput
from app.agents.feedback_agent import FeedbackAgent, FeedbackInput, FeedbackOutput
from app.agents.mcq_evaluation_agent import McqEvaluationAgent, McqInput, McqQuestionAnswer
from app.agents.similarity_agent import (
    SimilarityAgent, SimilarityCandidate, SimilarityInput,
)
from app.agents.sql_evaluation_agent import SqlEvaluationAgent, SqlEvaluationInput, SqlTestCase
from app.agents.theory_evaluation_agent import (
    RubricCriterionIn, TheoryEvaluationAgent, TheoryEvaluationInput,
)
from app.agents.token_similarity_agent import TokenCandidate, TokenSimilarityAgent, TokenSimilarityInput
from app.db.models.assignment import AssignmentType

_execution = ExecutionAgent()
_feedback = FeedbackAgent()
_similarity = SimilarityAgent()
_token_similarity = TokenSimilarityAgent()
_embedding_similarity = EmbeddingSimilarityAgent()
_mcq = McqEvaluationAgent()
_sql = SqlEvaluationAgent()
_theory = TheoryEvaluationAgent()


@dataclass
class PeerSubmission:
    student_id: str
    content: str


@dataclass
class SimilarityFinding:
    technique: str
    student_a: str
    student_b: str
    similarity: float


@dataclass
class PipelineContext:
    assignment_type: AssignmentType
    student_id: str
    submission_content: str
    language: str
    test_cases: list[dict]  # legacy-shaped — see submission_service._to_legacy_test_case (programming/SQL)
    assignment_description: str
    timeout_seconds: int
    peer_submissions: list[PeerSubmission] = field(default_factory=list)
    # Type-specific inputs the Programming pipeline doesn't need — assembled by
    # submission_service.py per assignment type. See each type's step function
    # for what it reads out of here.
    extra: dict = field(default_factory=dict)

    ingestion_ok: bool = True
    ingestion_note: str | None = None
    exec_result: ExecutionOutput | None = None
    feedback_result: FeedbackOutput | None = None
    # One entry per technique that actually ran (AST/token/embedding) — see
    # module docstring for why every technique reports separately rather than
    # collapsing into one score. Populated by _step_similarity_* below.
    similarity_findings: list[SimilarityFinding] = field(default_factory=list)
    similarity_notes: list[str] = field(default_factory=list)
    log: list[str] = field(default_factory=list)

    # Normalized outputs every pipeline converges on — see module docstring.
    final_status: str = "ok"
    final_score: float = 0.0
    final_total_points: float = 0.0
    final_breakdown: list[dict] = field(default_factory=list)
    final_feedback_text: str = ""
    final_failing_tests: list[str] = field(default_factory=list)


def _write_temp_py(content: str) -> str:
    """Used only by the Similarity step below — the AST-based technique it uses
    is still file-based/Python-only (unchanged since Phase 0; Phase 7's planned
    token/embedding techniques will need to handle other languages too, this
    doesn't yet)."""
    fd, path = tempfile.mkstemp(suffix=".py")
    with os.fdopen(fd, "w") as f:
        f.write(content)
    return path


# ---------------------------------------------------------------------------
# Programming pipeline (Phase 4/5)
# ---------------------------------------------------------------------------

def _step_ingestion(ctx: PipelineContext) -> None:
    if not ctx.submission_content.strip():
        ctx.ingestion_ok = False
        ctx.ingestion_note = "Empty submission."
        ctx.log.append("ingestion: REJECTED (empty)")
        return
    if ctx.language != "python":
        ctx.log.append(f"ingestion: OK ({ctx.language} — syntax checked at compile time)")
        return
    try:
        ast.parse(ctx.submission_content)
        ctx.log.append("ingestion: OK")
    except SyntaxError as e:
        ctx.log.append(f"ingestion: OK (will crash at execution — {e})")


def _step_execution(ctx: PipelineContext) -> None:
    ctx.exec_result = _execution.run(ExecutionInput(
        language=ctx.language, submission_content=ctx.submission_content,
        test_cases=ctx.test_cases, timeout_seconds=ctx.timeout_seconds,
    ))
    ctx.log.append(f"execution: status={ctx.exec_result.status}")


def _step_feedback(ctx: PipelineContext) -> None:
    ctx.feedback_result = _feedback.run(FeedbackInput(
        student_id=ctx.student_id, exec_result=ctx.exec_result, test_cases=ctx.test_cases,
        assignment_description=ctx.assignment_description, language=ctx.language,
    ))
    ctx.log.append(f"feedback: score={ctx.feedback_result.score}/{ctx.feedback_result.total_points}")


def _step_finalize_from_feedback(ctx: PipelineContext) -> None:
    """Shared by Programming and SQL — both produce a FeedbackOutput via the same
    FeedbackAgent (SQL's evaluator emits the same ExecutionOutput shape every
    LanguageRunner does — see sql_evaluation_agent.py's docstring for why)."""
    fb = ctx.feedback_result
    if fb is None:
        ctx.final_status = "rejected"
        ctx.final_feedback_text = ctx.ingestion_note or "Submission could not be evaluated."
        return
    ctx.final_status = fb.exec_status
    ctx.final_score = fb.score
    ctx.final_total_points = fb.total_points
    ctx.final_breakdown = [b.model_dump() for b in fb.breakdown]
    ctx.final_feedback_text = fb.feedback
    ctx.final_failing_tests = fb.failing_tests


def _step_similarity_ast(ctx: PipelineContext) -> None:
    paths = []
    try:
        candidates = []
        for peer in ctx.peer_submissions:
            p = _write_temp_py(peer.content)
            paths.append(p)
            candidates.append(SimilarityCandidate(student_id=peer.student_id, path=p, ok=True))
        p = _write_temp_py(ctx.submission_content)
        paths.append(p)
        candidates.append(SimilarityCandidate(student_id=ctx.student_id, path=p, ok=True))

        result = _similarity.run(SimilarityInput(submissions=candidates))
        for pair in result.flagged_pairs:
            ctx.similarity_findings.append(SimilarityFinding("ast", pair.student_a, pair.student_b, pair.similarity))
        ctx.similarity_notes.append(f"ast: {result.note}")
        ctx.log.append(f"similarity_ast: {len(result.flagged_pairs)} pair(s) flagged")
    finally:
        for p in paths:
            os.unlink(p)


def _step_similarity_token(ctx: PipelineContext) -> None:
    candidates = [TokenCandidate(student_id=p.student_id, content=p.content) for p in ctx.peer_submissions]
    candidates.append(TokenCandidate(student_id=ctx.student_id, content=ctx.submission_content))
    result = _token_similarity.run(TokenSimilarityInput(submissions=candidates))
    for pair in result.flagged_pairs:
        ctx.similarity_findings.append(SimilarityFinding("token", pair.student_a, pair.student_b, pair.similarity))
    ctx.similarity_notes.append(f"token: {result.note}")
    ctx.log.append(f"similarity_token: {len(result.flagged_pairs)} pair(s) flagged")


def _step_similarity_embedding(ctx: PipelineContext) -> None:
    candidates = [EmbeddingCandidate(student_id=p.student_id, content=p.content) for p in ctx.peer_submissions]
    candidates.append(EmbeddingCandidate(student_id=ctx.student_id, content=ctx.submission_content))
    result = _embedding_similarity.run(EmbeddingSimilarityInput(submissions=candidates))
    if result.skipped:
        ctx.similarity_notes.append(f"embedding: {result.note}")
        ctx.log.append("similarity_embedding: SKIPPED (model unavailable — see agent docstring)")
        return
    for pair in result.flagged_pairs:
        ctx.similarity_findings.append(
            SimilarityFinding("embedding", pair.student_a, pair.student_b, pair.similarity)
        )
    ctx.similarity_notes.append(f"embedding: {result.note}")
    ctx.log.append(f"similarity_embedding: {len(result.flagged_pairs)} pair(s) flagged")


def _skip_execution(ctx: PipelineContext) -> bool:
    return not ctx.ingestion_ok


def _skip_feedback(ctx: PipelineContext) -> bool:
    return ctx.exec_result is None


def _skip_similarity_ast(ctx: PipelineContext) -> bool:
    # Nothing to compare against with zero peer submissions — the concrete
    # "when an agent should be skipped" decision the architecture doc calls
    # out explicitly (§2.3). Also skipped for non-Python languages: the AST
    # technique this agent uses is Python-specific.
    return not ctx.ingestion_ok or len(ctx.peer_submissions) < 1 or ctx.language != "python"


def _skip_similarity_text(ctx: PipelineContext) -> bool:
    # Token/embedding techniques are language-agnostic (plain text), so unlike
    # AST they run for every language — the concrete example of Phase 7's
    # "similarity finally works for Java/C++/JS too."
    return not ctx.ingestion_ok or len(ctx.peer_submissions) < 1


# ---------------------------------------------------------------------------
# SQL pipeline (Phase 6) — reuses FeedbackAgent (see sql_evaluation_agent.py)
# ---------------------------------------------------------------------------

def _step_sql_execution(ctx: PipelineContext) -> None:
    sql_input = SqlEvaluationInput(
        schema_sql=ctx.extra["schema_sql"],
        seed_sql=ctx.extra.get("seed_sql", ""),
        submitted_query=ctx.submission_content,
        order_matters=ctx.extra.get("order_matters", False),
        test_cases=[SqlTestCase(**tc) for tc in ctx.extra["sql_test_cases"]],
    )
    ctx.exec_result = _sql.run(sql_input)
    ctx.log.append(f"sql_execution: status={ctx.exec_result.status}")


# ---------------------------------------------------------------------------
# MCQ pipeline (Phase 6) — single deterministic step
# ---------------------------------------------------------------------------

def _step_mcq_evaluate(ctx: PipelineContext) -> None:
    result = _mcq.run(McqInput(answers=[McqQuestionAnswer(**a) for a in ctx.extra["answers"]]))
    ctx.final_status = "ok"
    ctx.final_score = result.score
    ctx.final_total_points = result.total_points
    ctx.final_breakdown = [
        {"category": q.question_id, "earned": q.earned, "possible": q.possible, "detail": q.detail}
        for q in result.per_question
    ]
    ctx.final_feedback_text = result.feedback
    ctx.log.append(f"mcq_evaluate: {'PASS' if result.passed else 'FAIL'} "
                    f"({sum(1 for q in result.per_question if q.correct)}/{len(result.per_question)})")


# ---------------------------------------------------------------------------
# Theory pipeline (Phase 6) — LLM rubric scoring, honest offline "needs review"
# ---------------------------------------------------------------------------

def _step_theory_evaluate(ctx: PipelineContext) -> None:
    result = _theory.run(TheoryEvaluationInput(
        question=ctx.assignment_description,
        student_answer=ctx.submission_content,
        rubric_criteria=[RubricCriterionIn(**c) for c in ctx.extra["rubric_criteria"]],
    ))
    ctx.final_status = "ok" if result.graded else "needs_review"
    ctx.final_score = result.overall_score
    ctx.final_total_points = 1.0  # overall_score is already a 0-1 fraction of full rubric weight
    ctx.final_breakdown = [
        {"category": s.name, "earned": round(s.weight * s.fraction_earned, 4), "possible": s.weight}
        for s in result.criterion_scores
    ]
    ctx.final_feedback_text = result.feedback
    ctx.log.append(f"theory_evaluate: graded={result.graded} score={result.overall_score}")


@dataclass
class Step:
    name: str
    run: Callable[[PipelineContext], None]
    skip_if: Callable[[PipelineContext], bool]


# The decision table. Programming now has three similarity techniques, each
# with its own skip condition (AST is Python-only; token/embedding run for any
# language) — SQL/Theory/MCQ still don't run similarity at all (a natural
# follow-up: token/embedding techniques are language-agnostic text comparison,
# so there's no structural reason SQL queries couldn't be compared the same
# way — not done here to keep this phase scoped to widening the technique set,
# not widening which assignment types get similarity checking at all).
PIPELINE_GRAPH: dict[AssignmentType, list[Step]] = {
    AssignmentType.programming: [
        Step("ingestion", _step_ingestion, skip_if=lambda ctx: False),
        Step("execution", _step_execution, skip_if=_skip_execution),
        Step("feedback", _step_feedback, skip_if=_skip_feedback),
        Step("finalize", _step_finalize_from_feedback, skip_if=lambda ctx: False),
        Step("similarity_ast", _step_similarity_ast, skip_if=_skip_similarity_ast),
        Step("similarity_token", _step_similarity_token, skip_if=_skip_similarity_text),
        Step("similarity_embedding", _step_similarity_embedding, skip_if=_skip_similarity_text),
    ],
    AssignmentType.sql: [
        Step("sql_execution", _step_sql_execution, skip_if=lambda ctx: False),
        Step("feedback", _step_feedback, skip_if=lambda ctx: False),
        Step("finalize", _step_finalize_from_feedback, skip_if=lambda ctx: False),
    ],
    AssignmentType.mcq: [
        Step("mcq_evaluate", _step_mcq_evaluate, skip_if=lambda ctx: False),
    ],
    AssignmentType.theory: [
        Step("theory_evaluate", _step_theory_evaluate, skip_if=lambda ctx: False),
    ],
}


class OrchestratorV2:
    name = "orchestrator_v2"

    def run(self, ctx: PipelineContext) -> PipelineContext:
        graph = PIPELINE_GRAPH.get(ctx.assignment_type)
        if graph is None:
            raise ValueError(
                f"No pipeline defined yet for assignment type '{ctx.assignment_type.value}' "
                f"(case_study and design are Phase 6+ follow-ups) — programming, sql, mcq, and "
                f"theory are wired up end-to-end."
            )
        for step in graph:
            if step.skip_if(ctx):
                ctx.log.append(f"{step.name}: SKIPPED")
                continue
            step.run(ctx)
        return ctx

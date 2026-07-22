"""
Orchestrator — Phase 0 version.

Still a linear pipeline (Ingestion -> Execution -> Feedback -> Class Insight
-> Similarity), same shape as the original prototype, just calling the new
pydantic-wrapped agents instead of bare functions, and reading/writing
through legacy_store instead of inline file I/O.

This is deliberately NOT the decision-table state machine described in
the architecture doc (§2.3) — that's orchestrator_v2.py (Phase 4), used by
the real DB-backed submissions endpoint (submission_service.py). This
module is kept only for the legacy agents-demo router's file-based demo
data. Updated in Phase 5 to call ExecutionAgent's new content-based
signature (language + submission_content + test_cases, not file paths) —
that interface change is shared by both orchestrators since it lives in
execution_agent.py itself.
"""
import json
import os

from app.agents.ingestion_agent import IngestionAgent, IngestionInput
from app.agents.execution_agent import ExecutionAgent, ExecutionInput
from app.agents.feedback_agent import FeedbackAgent, FeedbackInput
from app.agents.class_insight_agent import ClassInsightAgent, InsightInput
from app.agents.similarity_agent import SimilarityAgent, SimilarityInput, SimilarityCandidate
from app.agents import legacy_store

_ingestion = IngestionAgent()
_execution = ExecutionAgent()
_feedback = FeedbackAgent()
_insight = ClassInsightAgent()
_similarity = SimilarityAgent()


def _merge_feedback(existing, new_entry):
    out = [e for e in existing if e["student_id"] != new_entry["student_id"]]
    out.append(new_entry)
    return out


def grade_one(assignment_id: str, student_id: str) -> dict:
    """Grades a single student's current submission — used for instant feedback
    on submit. Does not re-run class-wide insight/similarity (those are batch
    operations triggered explicitly via run_pipeline)."""
    paths = legacy_store.get_paths(assignment_id)
    meta = legacy_store.load_meta(assignment_id)
    test_cases = legacy_store.load_test_cases(assignment_id)
    sub_path = legacy_store.submission_path(assignment_id, student_id)

    if not os.path.exists(sub_path):
        raise FileNotFoundError(f"No submission found for {student_id}")

    with open(sub_path) as f:
        submission_content = f.read()

    exec_result = _execution.run(ExecutionInput(
        language="python",
        submission_content=submission_content,
        test_cases=test_cases,
        timeout_seconds=meta.get("timeout_seconds", 5),
    ))
    fb = _feedback.run(FeedbackInput(
        student_id=student_id,
        exec_result=exec_result,
        test_cases=test_cases,
        assignment_description=meta.get("description", ""),
    ))

    os.makedirs(paths["output"], exist_ok=True)
    feedback_path = os.path.join(paths["output"], "per_student_feedback.json")
    existing = []
    if os.path.exists(feedback_path):
        with open(feedback_path) as f:
            existing = json.load(f)
    with open(feedback_path, "w") as f:
        json.dump(_merge_feedback(existing, fb.model_dump()), f, indent=2)

    return fb.model_dump()


def run_pipeline(assignment_id: str, log=print) -> tuple[list[dict], dict, dict]:
    paths = legacy_store.get_paths(assignment_id)
    meta = legacy_store.load_meta(assignment_id)
    test_cases = legacy_store.load_test_cases(assignment_id)

    if not test_cases:
        raise ValueError(f"Assignment '{assignment_id}' has no test cases yet — add some "
                          f"before running the pipeline.")

    log("== Stage 1: Ingestion Agent ==")
    ingestion_out = _ingestion.run(IngestionInput(submissions_dir=paths["submissions"]))
    submissions = ingestion_out.items
    for s in submissions:
        flag = "OK" if s.ok else f"REJECTED ({s.note})"
        log(f"  {s.student_id:<12} {flag}")

    per_student_feedback = []

    log("\n== Stage 2+3: Execution Agent -> Feedback Agent ==")
    for s in submissions:
        if not s.ok:
            per_student_feedback.append({
                "student_id": s.student_id, "score": 0,
                "total_points": sum(tc.get("points", 1) for tc in test_cases),
                "breakdown": [], "exec_status": "rejected", "raw_error": None, "elapsed_ms": None,
                "failing_tests": [], "failing_details": [],
                "feedback": f"Submission rejected at ingestion: {s.note}",
            })
            log(f"  {s.student_id:<12} skipped execution (ingestion rejected)")
            continue

        with open(s.path) as f:
            submission_content = f.read()
        exec_result = _execution.run(ExecutionInput(
            language="python", submission_content=submission_content, test_cases=test_cases,
            timeout_seconds=meta.get("timeout_seconds", 5),
        ))
        fb = _feedback.run(FeedbackInput(
            student_id=s.student_id, exec_result=exec_result, test_cases=test_cases,
            assignment_description=meta.get("description", ""),
        ))
        per_student_feedback.append(fb.model_dump())
        log(f"  {s.student_id:<12} status={exec_result.status:<8} "
            f"score={fb.score}/{fb.total_points}  ({exec_result.elapsed_ms}ms)")

    log("\n== Stage 4: Class Insight Agent ==")
    insights = _insight.run(InsightInput(
        per_student_feedback=per_student_feedback, assignment_description=meta.get("description", ""),
    ))
    for c in insights.clusters:
        log(f"  [{len(c.student_ids)} students] {c.name}")
    for o in insights.outliers:
        log(f"  [outlier] {o.student_id}: {o.issue}")

    log("\n== Stage 5: Similarity Agent ==")
    similarity = _similarity.run(SimilarityInput(
        submissions=[SimilarityCandidate(student_id=s.student_id, path=s.path, ok=s.ok) for s in submissions],
    ))
    if similarity.flagged_pairs:
        for p in similarity.flagged_pairs:
            log(f"  {p.student_a} <-> {p.student_b}: {p.similarity:.0%} structural similarity")
    else:
        log("  No pairs above threshold.")

    os.makedirs(paths["output"], exist_ok=True)
    with open(os.path.join(paths["output"], "per_student_feedback.json"), "w") as f:
        json.dump(per_student_feedback, f, indent=2)
    with open(os.path.join(paths["output"], "class_insight.json"), "w") as f:
        json.dump(insights.model_dump(), f, indent=2)
    with open(os.path.join(paths["output"], "similarity_report.json"), "w") as f:
        json.dump(similarity.model_dump(), f, indent=2)

    log("\n== Stage 6: Reporting Layer ==")
    log(f"  Wrote {paths['output']}/per_student_feedback.json")
    log(f"  Wrote {paths['output']}/class_insight.json")
    log(f"  Wrote {paths['output']}/similarity_report.json")

    return per_student_feedback, insights.model_dump(), similarity.model_dump()

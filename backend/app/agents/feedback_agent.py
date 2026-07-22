"""
Feedback Agent — pydantic-wrapped port of the original feedback_agent.py.
Scoring logic (rubric-as-test-suite) and the offline deterministic fallback
are unchanged; only the calling convention is now typed I/O through run().

Fixed as part of Phase 6: the system prompt and offline crash message used
to hardcode "Python" — a latent bug since Phase 5 introduced Java/C++/JS
submissions reusing this same agent, and Phase 6's SQL branch made it more
visible. Both are language-generic now, driven by the new `language` field
on FeedbackInput.
"""
from collections import defaultdict

from pydantic import BaseModel

from app.agents.base import Agent
from app.agents.evaluation.schemas import ExecutionOutput
from app.agents import llm_client

SYSTEM_PROMPT = """You are an experienced, kind but precise teaching assistant grading a
programming/query assignment. Given the assignment description, the language, and the
automated test results for one student's submission, write feedback that:
1. States plainly what was attempted and what worked.
2. For each failure, explains the REASONING error (not just "test failed") — what
   misconception likely caused it.
3. Gives a concrete, specific pointer on how to fix it (not the full solution).
4. Is encouraging but honest. 120-180 words. No headers, just prose."""


class FeedbackInput(BaseModel):
    student_id: str
    exec_result: ExecutionOutput
    test_cases: list[dict]
    assignment_description: str = ""
    language: str = "python"


class FeedbackBreakdownItem(BaseModel):
    category: str
    earned: float
    possible: float


class FeedbackOutput(BaseModel):
    student_id: str
    score: float
    total_points: float
    breakdown: list[FeedbackBreakdownItem]
    exec_status: str
    raw_error: str | None = None
    elapsed_ms: float | None = None
    failing_tests: list[str]
    failing_details: list[dict]
    feedback: str


def _score(test_cases, results_by_id):
    total_earned, total_possible = 0.0, 0.0
    by_category = defaultdict(lambda: {"earned": 0.0, "possible": 0.0})
    for tc in test_cases:
        pts = tc.get("points", 1)
        total_possible += pts
        by_category[tc["category"]]["possible"] += pts
        result = results_by_id.get(tc["id"])
        if result and result["passed"]:
            total_earned += pts
            by_category[tc["category"]]["earned"] += pts
    breakdown = [{"category": cat, "earned": round(v["earned"], 2), "possible": round(v["possible"], 2)}
                 for cat, v in by_category.items()]
    return round(total_earned, 2), round(total_possible, 2), breakdown


_RUN_COMMAND_HINTS = {
    "python": "`python your_file.py`",
    "javascript": "`node your_file.js`",
    "java": "`javac Solution.java` (compile errors show exactly which line is wrong)",
    "cpp": "`g++ -std=c++17 your_file.cpp -o out` (compile errors show exactly which line is wrong)",
}


def _offline_feedback(exec_result: ExecutionOutput, breakdown, language: str = "python"):
    if exec_result.status == "timeout":
        return ("Your submission did not finish within the time limit, which almost always "
                "means an infinite loop — check that every loop variable you're using as a "
                "stopping condition actually gets updated on every iteration. Nothing could "
                "be graded past this point, so fix the loop termination logic first and "
                "resubmit.")
    if exec_result.status == "crash" and not exec_result.results:
        run_hint = _RUN_COMMAND_HINTS.get(language, f"running the {language} file locally")
        return (f"Your submission could not be run at all: {(exec_result.raw_error or '')[:200]}. "
                f"This is usually a syntax error or a typo in a function/method name that the "
                f"grader is looking for. Double check it runs locally with {run_hint} before "
                f"resubmitting — a submission that doesn't compile/import cannot be graded further.")

    if not breakdown:
        return "No test cases are defined for this assignment yet, so nothing could be graded."

    lines = []
    for item in breakdown:
        pct = 0 if item["possible"] == 0 else round(100 * item["earned"] / item["possible"])
        if pct == 100:
            lines.append(f"{item['category']} looks solid — full marks there.")
        elif pct == 0:
            lines.append(f"{item['category']} isn't working yet — none of those checks passed, "
                          f"which suggests a logic issue in that function rather than a small typo.")
        else:
            lines.append(f"{item['category']} is partially correct ({pct}%), meaning your core "
                          f"approach is right but at least one edge case isn't handled.")
    return " ".join(lines)


class FeedbackAgent(Agent[FeedbackInput, FeedbackOutput]):
    name = "feedback_agent"

    def run(self, payload: FeedbackInput) -> FeedbackOutput:
        exec_result = payload.exec_result
        results_by_id = {r["id"]: r for r in exec_result.results}
        score, total_points, breakdown = _score(payload.test_cases, results_by_id)

        if llm_client.is_live():
            failing = [r for r in exec_result.results if not r["passed"]]
            user_prompt = (
                f"Language: {payload.language}\n"
                f"Assignment description: {payload.assignment_description}\n\n"
                f"Execution status: {exec_result.status}\n"
                f"Raw error (if any): {exec_result.raw_error}\n"
                f"Test results: {exec_result.results}\n"
                f"Failing tests detail: {failing}\n"
                f"Score awarded: {score} / {total_points}\n\n"
                f"Write the feedback now."
            )
            text = llm_client.complete(SYSTEM_PROMPT, user_prompt) or _offline_feedback(
                exec_result, breakdown, payload.language,
            )
        else:
            text = _offline_feedback(exec_result, breakdown, payload.language)

        return FeedbackOutput(
            student_id=payload.student_id,
            score=score,
            total_points=total_points,
            breakdown=[FeedbackBreakdownItem(**b) for b in breakdown],
            exec_status=exec_result.status,
            raw_error=exec_result.raw_error,
            elapsed_ms=exec_result.elapsed_ms,
            failing_tests=[r["id"] for r in exec_result.results if not r["passed"]],
            failing_details=[
                {"id": r["id"], "category": r["category"], "error": r["error"]}
                for r in exec_result.results if not r["passed"]
            ],
            feedback=text,
        )

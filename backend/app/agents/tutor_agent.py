"""
Tutor Agent — Phase 10.

Answers student questions about their own submission/course material.
NEVER reveals a complete solution — enforced in the system prompt (LLM
path) and structurally in the offline fallback (which only ever echoes
back the student's OWN test-execution results, never a reference
solution or expected values it doesn't have access to in the first
place — there is no code path here that could leak one).

Unlike Theory Agent's offline fallback (Phase 6, a flat "needs manual
review" — free-text grading has no meaningful offline approximation), the
Tutor's offline fallback is genuinely useful: "why did testcase 4 fail"
has a deterministic answer sitting right in the submission's own
execution results, which don't require an LLM to retrieve and present.
Only the *conversational, explanatory* layer needs an LLM — the raw facts
don't.
"""
import re

from pydantic import BaseModel

from app.agents.base import Agent
from app.agents import llm_client

SYSTEM_PROMPT = """You are a patient, encouraging teaching assistant helping a student
understand their own work. You will be given: the assignment description, the student's
question, their submission's execution/test results (if relevant), retrieved course material
excerpts (if relevant and available), recent conversation history, and any recurring mistake
patterns from their past work in this course.

CRITICAL RULE: NEVER reveal a complete solution, a full corrected code snippet, or the exact
expected output/answer for a test case. Instead:
- Explain WHY something failed (the underlying misconception), not just THAT it failed.
- Give a progressive hint — point toward the right concept or the specific line/area to
  reconsider, without writing the fix for them.
- If they ask for "the answer" directly, redirect toward understanding: explain the concept,
  suggest what to look at, but do not provide code or the specific correct value.
- If recurring mistake patterns are provided, gently connect today's question to that pattern
  when relevant ("this looks similar to what came up in your last submission...").
- If retrieved course material is provided and relevant, ground your answer in it and mention
  the source file naturally.
- Keep answers focused and conversational, 80-150 words, no headers."""


class ExecutionContext(BaseModel):
    exec_status: str
    failing_tests: list[dict] = []  # [{"id", "category", "error"}, ...]
    score: float | None = None
    total_points: float | None = None


class RetrievedContext(BaseModel):
    text: str
    filename: str | None = None


class TutorInput(BaseModel):
    student_question: str
    assignment_description: str = ""
    submission_context: ExecutionContext | None = None
    retrieved_chunks: list[RetrievedContext] = []
    recent_messages: list[dict] = []  # [{"role": "user"|"tutor", "content": str}, ...]
    recurring_mistake_categories: list[str] = []


class TutorOutput(BaseModel):
    answer: str
    used_rag: bool
    used_llm: bool


_TESTCASE_NUMBER_RE = re.compile(r"test\s*case\s*#?(\d+)|testcase\s*#?(\d+)", re.IGNORECASE)


def _offline_answer(payload: TutorInput) -> str:
    """Deterministic, fact-based fallback — see module docstring for why this is
    genuinely useful rather than a dead end, unlike Theory Agent's offline mode."""
    ctx = payload.submission_context
    if ctx is None:
        return (
            "AI tutoring conversations need an LLM provider configured (set GEMINI_API_KEY "
            "or GROQ_API_KEY) to have a real back-and-forth — none is configured right now. "
            "If your question is about a specific submission, ask it from that submission's "
            "page and I can at least show you your own test results directly."
        )

    if ctx.exec_status == "timeout":
        return ("Your submission timed out, which almost always means an infinite loop — "
                "check that every loop's stopping condition actually changes on each "
                "iteration. (Full AI tutoring needs an LLM provider configured for anything "
                "beyond this kind of direct fact.)")

    if not ctx.failing_tests:
        return (f"Your submission passed everything it was tested on ({ctx.score}/{ctx.total_points} points) "
                f"— nothing to debug here. (Full AI tutoring needs an LLM provider configured for "
                f"open-ended questions.)")

    # If the question references a specific test case number, try to answer that directly.
    match = _TESTCASE_NUMBER_RE.search(payload.student_question)
    if match:
        idx = int(match.group(1) or match.group(2)) - 1
        if 0 <= idx < len(ctx.failing_tests):
            t = ctx.failing_tests[idx]
            return (f"Test case {idx + 1} (category: {t.get('category', 'general')}) failed with: "
                    f"{t.get('error', 'no error detail available')}. (This is the raw result — full "
                    f"AI tutoring needs an LLM provider configured for a deeper explanation.)")

    lines = [f"- {t.get('category', 'general')}: {t.get('error', 'failed')}" for t in ctx.failing_tests[:5]]
    return (
        f"Here's what's currently failing ({ctx.score}/{ctx.total_points} points):\n" + "\n".join(lines) +
        "\n(Raw results — full AI tutoring needs an LLM provider configured for a real explanation.)"
    )


class TutorAgent(Agent[TutorInput, TutorOutput]):
    name = "tutor_agent"

    def run(self, payload: TutorInput) -> TutorOutput:
        if not llm_client.is_live():
            return TutorOutput(answer=_offline_answer(payload), used_rag=False, used_llm=False)

        parts = [f"Assignment: {payload.assignment_description}", f"Student question: {payload.student_question}"]
        if payload.submission_context:
            parts.append(f"Submission results: {payload.submission_context.model_dump()}")
        if payload.recurring_mistake_categories:
            parts.append(f"Recurring mistake categories from past work: {payload.recurring_mistake_categories}")
        if payload.retrieved_chunks:
            excerpts = "\n---\n".join(f"[{c.filename or 'course material'}]: {c.text[:800]}" for c in payload.retrieved_chunks)
            parts.append(f"Retrieved course material:\n{excerpts}")
        if payload.recent_messages:
            history = "\n".join(f"{m['role']}: {m['content']}" for m in payload.recent_messages[-6:])
            parts.append(f"Recent conversation:\n{history}")

        text = llm_client.complete(SYSTEM_PROMPT, "\n\n".join(parts), max_tokens=400)
        if not text:
            return TutorOutput(answer=_offline_answer(payload), used_rag=False, used_llm=False)

        return TutorOutput(answer=text, used_rag=bool(payload.retrieved_chunks), used_llm=True)

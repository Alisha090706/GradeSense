"""
Theory Evaluation Agent — LLM rubric scoring for free-text answers.

Unlike every other evaluation path in this codebase, there is NO offline
fallback here that produces a real grade — the whole prototype's
offline-mode philosophy (a rule-based approximation of what the LLM would
say, so the platform stays usable with zero API keys) doesn't have a
meaningful equivalent for "is this paragraph a correct explanation of
B-tree rebalancing." Rather than fabricate a fake heuristic score that
would look like real grading, no LLM configured means the submission is
marked `graded=False` with a clear "needs manual review" status — an
honest degraded mode instead of a confident-looking wrong one.
"""
import json
import re

from pydantic import BaseModel

from app.agents.base import Agent
from app.agents import llm_client

SYSTEM_PROMPT = """You are grading a free-text answer to a theory/conceptual question against a
weighted rubric. For EACH rubric criterion, give a score from 0.0 to 1.0 (fraction of that
criterion's weight earned) and a one-sentence justification. Then write 2-4 sentences of
overall feedback: what the answer got right, what's missing or wrong, phrased constructively.
Do not reveal a "correct answer" the student could copy — describe gaps, don't fill them in.
Respond ONLY as valid JSON: {"criterion_scores": [{"name": str, "score": 0.0-1.0, "comment": str}],
"feedback": str}. No prose outside the JSON."""


class RubricCriterionIn(BaseModel):
    name: str
    weight: float


class TheoryEvaluationInput(BaseModel):
    question: str
    student_answer: str
    rubric_criteria: list[RubricCriterionIn]


class CriterionScore(BaseModel):
    name: str
    weight: float
    fraction_earned: float
    comment: str = ""


class TheoryEvaluationOutput(BaseModel):
    graded: bool
    overall_score: float  # 0.0-1.0, weighted sum of criterion fraction_earned * weight
    criterion_scores: list[CriterionScore]
    feedback: str


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    return json.loads(text)


class TheoryEvaluationAgent(Agent[TheoryEvaluationInput, TheoryEvaluationOutput]):
    name = "theory_evaluation_agent"

    def run(self, payload: TheoryEvaluationInput) -> TheoryEvaluationOutput:
        if not payload.student_answer.strip():
            return TheoryEvaluationOutput(
                graded=True, overall_score=0.0,
                criterion_scores=[
                    CriterionScore(name=c.name, weight=c.weight, fraction_earned=0.0, comment="No answer submitted.")
                    for c in payload.rubric_criteria
                ],
                feedback="No answer was submitted.",
            )

        if not llm_client.is_live():
            return TheoryEvaluationOutput(
                graded=False, overall_score=0.0,
                criterion_scores=[
                    CriterionScore(name=c.name, weight=c.weight, fraction_earned=0.0) for c in payload.rubric_criteria
                ],
                feedback=(
                    "This answer needs manual review — automatic grading of free-text theory "
                    "answers requires an LLM provider (set GEMINI_API_KEY or GROQ_API_KEY), and "
                    "none is configured. A teacher should grade this submission directly."
                ),
            )

        criteria_str = ", ".join(f"{c.name} (weight {c.weight})" for c in payload.rubric_criteria)
        user_prompt = (
            f"Question: {payload.question}\n\nRubric criteria: {criteria_str}\n\n"
            f"Student answer:\n{payload.student_answer}\n\nGrade it now."
        )
        text = llm_client.complete(SYSTEM_PROMPT, user_prompt, max_tokens=700)
        if not text:
            return self.run(TheoryEvaluationInput(
                question=payload.question, student_answer="", rubric_criteria=payload.rubric_criteria,
            ))  # unreachable in practice (is_live() already checked) — safety net only

        try:
            parsed = _extract_json(text)
            weight_by_name = {c.name: c.weight for c in payload.rubric_criteria}
            scores = [
                CriterionScore(
                    name=cs["name"], weight=weight_by_name.get(cs["name"], 0.0),
                    fraction_earned=max(0.0, min(1.0, cs["score"])), comment=cs.get("comment", ""),
                )
                for cs in parsed["criterion_scores"]
            ]
            overall = sum(s.weight * s.fraction_earned for s in scores)
            return TheoryEvaluationOutput(
                graded=True, overall_score=round(overall, 4), criterion_scores=scores,
                feedback=parsed.get("feedback", ""),
            )
        except Exception:
            return TheoryEvaluationOutput(
                graded=False, overall_score=0.0,
                criterion_scores=[
                    CriterionScore(name=c.name, weight=c.weight, fraction_earned=0.0) for c in payload.rubric_criteria
                ],
                feedback="Automatic grading failed to produce a valid result — a teacher should review this submission directly.",
            )

"""
MCQ Evaluation Agent — deterministic key match, per question.

An MCQ assignment stores its questions directly on Assignment.constraints
(the JSONB field every Assignment already has):

    {"questions": [
        {"id": "q1", "text": "...", "options": {"A": "...", "B": "..."},
         "correct_options": ["B"], "points": 1},
        {"id": "q2", "text": "...", "options": {"A": "...", ...},
         "correct_options": ["A", "C"], "points": 2},  # multi-select
        ...
    ]}

`correct_options` is always a list (even for a single-answer question) so
one schema covers both single- and multi-select without a separate code
path. A submission's `content` is a JSON object mapping each question id
to the list of option keys the student selected, e.g.
`{"q1": ["B"], "q2": ["A", "C"]}`.

Each question is graded independently and requires an exact set match
(selected == correct, order-insensitive) for credit — no partial credit
for a multi-select question with some-but-not-all correct options ticked,
which keeps the grading rule simple and unambiguous to students. Total
score is the sum of points earned across all questions.
"""
from pydantic import BaseModel

from app.agents.base import Agent


class McqQuestionAnswer(BaseModel):
    question_id: str
    question_text: str = ""
    selected: list[str]
    correct: list[str]
    points: float = 1


class McqInput(BaseModel):
    answers: list[McqQuestionAnswer]


class McqQuestionResult(BaseModel):
    question_id: str
    correct: bool
    earned: float
    possible: float
    detail: str


class McqOutput(BaseModel):
    passed: bool  # true iff every question was answered correctly
    score: float
    total_points: float
    feedback: str
    per_question: list[McqQuestionResult]


def _normalize(options: list[str]) -> set[str]:
    return {o.strip().upper() for o in options}


class McqEvaluationAgent(Agent[McqInput, McqOutput]):
    name = "mcq_evaluation_agent"

    def run(self, payload: McqInput) -> McqOutput:
        per_question: list[McqQuestionResult] = []
        score = 0.0
        total_points = 0.0
        all_correct = True

        for answer in payload.answers:
            selected = _normalize(answer.selected)
            correct = _normalize(answer.correct)
            is_correct = selected == correct
            earned = answer.points if is_correct else 0.0
            score += earned
            total_points += answer.points
            all_correct = all_correct and is_correct
            per_question.append(McqQuestionResult(
                question_id=answer.question_id,
                correct=is_correct,
                earned=earned,
                possible=answer.points,
                detail=(
                    "Correct." if is_correct
                    else f"You selected {sorted(selected) or ['(none)']}; "
                         f"the correct answer was {sorted(correct)}."
                ),
            ))

        num_correct = sum(1 for r in per_question if r.correct)
        feedback = (
            "All questions correct." if all_correct
            else f"{num_correct}/{len(per_question)} questions correct."
        )
        return McqOutput(
            passed=all_correct, score=score, total_points=total_points,
            feedback=feedback, per_question=per_question,
        )

"""agents/mcq_evaluation_agent.py — matching option case/whitespace
insensitively (per the original Phase 6 check), extended for multi-question
and multi-select support (each question graded independently, exact set
match required per question)."""
from app.agents.mcq_evaluation_agent import McqEvaluationAgent, McqInput, McqQuestionAnswer


class TestMcqEvaluationAgent:
    def setup_method(self):
        self.agent = McqEvaluationAgent()

    def test_exact_match_passes(self):
        result = self.agent.run(McqInput(answers=[
            McqQuestionAnswer(question_id="q1", selected=["B"], correct=["B"], points=1),
        ]))
        assert result.passed is True
        assert result.score == 1

    def test_case_insensitive_match_passes(self):
        result = self.agent.run(McqInput(answers=[
            McqQuestionAnswer(question_id="q1", selected=["b"], correct=["B"], points=2),
        ]))
        assert result.passed is True
        assert result.score == 2

    def test_whitespace_is_stripped(self):
        result = self.agent.run(McqInput(answers=[
            McqQuestionAnswer(question_id="q1", selected=[" B "], correct=["B"], points=1),
        ]))
        assert result.passed is True

    def test_wrong_answer_scores_zero(self):
        result = self.agent.run(McqInput(answers=[
            McqQuestionAnswer(question_id="q1", selected=["C"], correct=["B"], points=1),
        ]))
        assert result.passed is False
        assert result.score == 0
        assert result.total_points == 1

    def test_multi_select_requires_exact_set(self):
        # Selecting only one of two correct options earns nothing for that question —
        # no partial credit, per the agent's documented grading rule.
        result = self.agent.run(McqInput(answers=[
            McqQuestionAnswer(question_id="q1", selected=["A"], correct=["A", "C"], points=2),
        ]))
        assert result.passed is False
        assert result.score == 0
        assert result.per_question[0].correct is False

    def test_multi_select_exact_match_passes_regardless_of_order(self):
        result = self.agent.run(McqInput(answers=[
            McqQuestionAnswer(question_id="q1", selected=["C", "A"], correct=["A", "C"], points=2),
        ]))
        assert result.passed is True
        assert result.score == 2

    def test_multiple_questions_scored_independently(self):
        result = self.agent.run(McqInput(answers=[
            McqQuestionAnswer(question_id="q1", selected=["B"], correct=["B"], points=1),
            McqQuestionAnswer(question_id="q2", selected=["A"], correct=["B"], points=2),
        ]))
        assert result.passed is False  # not ALL questions correct
        assert result.score == 1
        assert result.total_points == 3
        assert len(result.per_question) == 2
        assert result.per_question[0].correct is True
        assert result.per_question[1].correct is False

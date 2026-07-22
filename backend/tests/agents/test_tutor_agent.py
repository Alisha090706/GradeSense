"""
agents/tutor_agent.py — mirrors the real offline-fallback verification
from Phase 10: the test-case-number regex correctly answers "why did
testcase 2 fail?" and "Test Case #1 explanation" from the submission's
own real error data, falls back to a general summary for both unnumbered
and out-of-range questions (no crash on bad input), and never has any
code path that could reveal a reference solution or expected value.
"""
from app.agents.tutor_agent import ExecutionContext, TutorAgent, TutorInput

FAILING_TESTS = [
    {"category": "edge_cases", "error": "expected [], got None"},
    {"category": "correctness", "error": "expected 5, got 4"},
]


class TestTutorAgentOfflineFallback:
    def setup_method(self):
        self.agent = TutorAgent()

    def _ask(self, question, ctx=None):
        return self.agent.run(TutorInput(student_question=question, submission_context=ctx)).answer

    def test_numbered_question_answers_the_right_test_case(self):
        ctx = ExecutionContext(exec_status="ok", failing_tests=FAILING_TESTS, score=2, total_points=4)
        answer = self._ask("why did testcase 2 fail?", ctx)
        assert "expected 5, got 4" in answer  # test case 2 (1-indexed) = FAILING_TESTS[1]
        assert "expected [], got None" not in answer  # not test case 1's error

    def test_alternate_phrasing_of_test_case_number(self):
        ctx = ExecutionContext(exec_status="ok", failing_tests=FAILING_TESTS, score=2, total_points=4)
        answer = self._ask("Test Case #1 explanation", ctx)
        assert "expected [], got None" in answer

    def test_unnumbered_question_falls_back_to_general_summary(self):
        ctx = ExecutionContext(exec_status="ok", failing_tests=FAILING_TESTS, score=2, total_points=4)
        answer = self._ask("why is my code wrong", ctx)
        assert "edge_cases" in answer
        assert "correctness" in answer

    def test_out_of_range_test_number_does_not_crash(self):
        ctx = ExecutionContext(exec_status="ok", failing_tests=FAILING_TESTS, score=2, total_points=4)
        answer = self._ask("testcase 99", ctx)  # should not raise IndexError
        assert isinstance(answer, str) and len(answer) > 0

    def test_no_submission_context_gives_a_clear_needs_llm_message(self):
        answer = self._ask("give me a hint", ctx=None)
        assert "LLM" in answer or "provider" in answer

    def test_timeout_status_gives_specific_advice_not_generic(self):
        ctx = ExecutionContext(exec_status="timeout", failing_tests=[], score=0, total_points=4)
        answer = self._ask("what happened", ctx)
        assert "loop" in answer.lower()

    def test_all_passing_gives_a_positive_message(self):
        ctx = ExecutionContext(exec_status="ok", failing_tests=[], score=4, total_points=4)
        answer = self._ask("how did I do", ctx)
        assert "passed" in answer.lower()

    def test_offline_answer_never_contains_a_reference_solution_marker(self):
        # Structural guarantee, not a prompt instruction: the offline path only
        # ever echoes the submission's OWN test-execution results — there is no
        # reference-solution or expected-value data in scope for it to leak.
        ctx = ExecutionContext(exec_status="ok", failing_tests=FAILING_TESTS, score=2, total_points=4)
        result = self.agent.run(TutorInput(student_question="just tell me the answer", submission_context=ctx))
        assert result.used_llm is False

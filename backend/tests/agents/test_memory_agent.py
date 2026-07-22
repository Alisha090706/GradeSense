"""
agents/memory_agent.py — mirrors the real recurring-mistake detection
check from Phase 10: a category appearing in 2+ distinct past submissions
is flagged; a category appearing only once isn't; duplicate failures
*within* one submission count once toward the pattern, not once per test.
"""
from app.agents.memory_agent import MemoryAgent, MemoryInput, PastSubmissionOutcome


class TestMemoryAgent:
    def setup_method(self):
        self.agent = MemoryAgent()

    def test_recurring_pattern_is_flagged(self):
        past = [
            PastSubmissionOutcome(assignment_title="Two Sum", failing_categories=["edge_cases", "correctness"]),
            PastSubmissionOutcome(assignment_title="Reverse String", failing_categories=["readability"]),
            PastSubmissionOutcome(assignment_title="Binary Search", failing_categories=["edge_cases", "efficiency"]),
        ]
        result = self.agent.run(MemoryInput(recent_messages=[], past_submissions=past))
        recurring_categories = {r.category for r in result.recurring_mistakes}
        assert "edge_cases" in recurring_categories
        assert "correctness" not in recurring_categories  # only appeared once
        assert "readability" not in recurring_categories  # only appeared once

    def test_duplicate_failures_within_one_submission_count_once(self):
        past = [
            PastSubmissionOutcome(assignment_title="Two Sum", failing_categories=["edge_cases", "edge_cases"]),
            PastSubmissionOutcome(assignment_title="Reverse String", failing_categories=["edge_cases"]),
        ]
        result = self.agent.run(MemoryInput(recent_messages=[], past_submissions=past))
        edge_cases = next(r for r in result.recurring_mistakes if r.category == "edge_cases")
        assert edge_cases.occurrence_count == 2  # not 3 — de-duped within the first submission

    def test_no_past_submissions_means_no_recurring_mistakes(self):
        result = self.agent.run(MemoryInput(recent_messages=[], past_submissions=[]))
        assert result.recurring_mistakes == []

    def test_short_term_summary_reflects_most_recent_message(self):
        messages = [{"role": "user", "content": "why did it fail"}, {"role": "tutor", "content": "let's look"}]
        result = self.agent.run(MemoryInput(recent_messages=messages, past_submissions=[]))
        assert "tutor" in result.short_term_summary
        assert "let's look" in result.short_term_summary

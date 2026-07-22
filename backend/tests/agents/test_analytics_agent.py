"""
agents/analytics_agent.py — mirrors the real aggregation-math session from
Phase 8: score distribution bucketing, category-failure ranking, and —
the one most worth a permanent regression test — the course-level average
being submission-count-weighted rather than a flat mean of per-assignment
averages (a 2-student assignment must not pull the course average as hard
as a 10-student one).
"""
from app.agents.analytics_agent import (
    AssignmentAnalyticsAgent, AssignmentAnalyticsInput, AssignmentPerformanceSummary,
    CourseAnalyticsAgent, CourseAnalyticsInput, SubmissionSummary,
)


class TestAssignmentAnalyticsAgent:
    def setup_method(self):
        self.agent = AssignmentAnalyticsAgent()

    def test_empty_submissions_returns_null_average(self):
        result = self.agent.run(AssignmentAnalyticsInput(
            assignment_title="Two Sum", submissions=[], plagiarism_flagged_pair_count=0,
        ))
        assert result.submission_count == 0
        assert result.average_score_pct is None

    def test_average_and_distribution(self):
        submissions = [
            SubmissionSummary(student_id="s1", score=4, total_points=4, exec_status="ok", failing_categories=[]),
            SubmissionSummary(student_id="s2", score=2, total_points=4, exec_status="ok",
                               failing_categories=["edge_cases", "efficiency"]),
            SubmissionSummary(student_id="s3", score=0, total_points=4, exec_status="ok",
                               failing_categories=["correctness", "edge_cases"]),
            SubmissionSummary(student_id="s4", score=3, total_points=4, exec_status="ok",
                               failing_categories=["edge_cases"]),
        ]
        result = self.agent.run(AssignmentAnalyticsInput(
            assignment_title="Two Sum", submissions=submissions, plagiarism_flagged_pair_count=0,
        ))
        assert result.average_score_pct == 56.2  # (100 + 50 + 0 + 75) / 4
        assert result.most_failed_category == "edge_cases"  # appears in 3 of 4 submissions
        rates_by_category = {r.category: r.failure_count for r in result.category_failure_rates}
        assert rates_by_category["edge_cases"] == 3
        assert rates_by_category["efficiency"] == 1


class TestCourseAnalyticsAgent:
    def setup_method(self):
        self.agent = CourseAnalyticsAgent()

    def test_average_is_weighted_by_submission_count_not_flat_mean(self):
        summaries = [
            AssignmentPerformanceSummary(assignment_id="a1", title="A1", average_score_pct=90, submission_count=10),
            AssignmentPerformanceSummary(assignment_id="a2", title="A2", average_score_pct=50, submission_count=2),
        ]
        result = self.agent.run(CourseAnalyticsInput(
            course_name="Intro to DSA", assignment_summaries=summaries, total_plagiarism_flagged_pair_count=0,
        ))
        flat_mean = (90 + 50) / 2  # 70.0 — what a naive implementation would give
        assert result.average_score_pct == 83.3
        assert result.average_score_pct != flat_mean
        assert result.average_score_pct > flat_mean  # pulled toward the larger class, not away from it

    def test_weakest_assignment_is_the_lowest_scoring_one(self):
        summaries = [
            AssignmentPerformanceSummary(assignment_id="a1", title="A1", average_score_pct=90, submission_count=10),
            AssignmentPerformanceSummary(assignment_id="a2", title="A2", average_score_pct=50, submission_count=2),
        ]
        result = self.agent.run(CourseAnalyticsInput(
            course_name="Intro to DSA", assignment_summaries=summaries, total_plagiarism_flagged_pair_count=0,
        ))
        assert result.weakest_assignment == "A2"

    def test_ungraded_assignments_dont_break_the_average(self):
        summaries = [
            AssignmentPerformanceSummary(assignment_id="a1", title="A1", average_score_pct=90, submission_count=10),
            AssignmentPerformanceSummary(assignment_id="a2", title="A2", average_score_pct=None, submission_count=0),
        ]
        result = self.agent.run(CourseAnalyticsInput(
            course_name="Intro to DSA", assignment_summaries=summaries, total_plagiarism_flagged_pair_count=0,
        ))
        assert result.average_score_pct == 90.0

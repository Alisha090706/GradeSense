"""
Analytics Agent — Phase 8.

Generalizes class_insight_agent.py (Phase 0, still single-assignment
misconception clustering, unchanged) up to the course level: average
score, topic-wise (per-assignment, in this schema's absence of a separate
"topic" concept — see AssignmentAnalyticsAgent's docstring) performance,
most-failed test case, plagiarism statistics.

Two agents, not one — AssignmentAnalyticsAgent computes metrics for a
single assignment's submissions; CourseAnalyticsAgent aggregates across
a course's assignments. Both are pure computation over plain lists (no DB
access), same as every other agent in this codebase — analytics_service.py
owns fetching DB rows and persisting the result into AnalyticsSnapshot
(the table that's existed since Phase 0's schema but was never written to
until this phase).
"""
from collections import defaultdict

from pydantic import BaseModel

from app.agents.base import Agent


class SubmissionSummary(BaseModel):
    student_id: str
    score: float
    total_points: float
    exec_status: str
    failing_categories: list[str] = []


class AssignmentAnalyticsInput(BaseModel):
    assignment_title: str
    submissions: list[SubmissionSummary]
    plagiarism_flagged_pair_count: int


class CategoryFailureRate(BaseModel):
    category: str
    failure_count: int
    failure_rate: float  # 0.0-1.0, fraction of submissions that failed this category


class ScoreDistributionBucket(BaseModel):
    range_label: str  # e.g. "0-25%"
    count: int


class AssignmentAnalyticsOutput(BaseModel):
    assignment_title: str
    submission_count: int
    average_score_pct: float | None
    score_distribution: list[ScoreDistributionBucket]
    most_failed_category: str | None
    category_failure_rates: list[CategoryFailureRate]
    plagiarism_flagged_pair_count: int


_DISTRIBUTION_BUCKETS = [(0, 25), (25, 50), (50, 75), (75, 90), (90, 101)]


def _bucket_label(lo: int, hi: int) -> str:
    return f"{lo}-100%" if hi > 100 else f"{lo}-{hi}%"


class AssignmentAnalyticsAgent(Agent[AssignmentAnalyticsInput, AssignmentAnalyticsOutput]):
    """"Topic-wise performance" at the assignment level manifests as per-category
    (per test-case-category / per-rubric-criterion) failure rates — there's no
    separate "topic" field in the schema beyond what a category name already
    captures, so this reports at that granularity rather than inventing a new
    concept the data doesn't actually have."""
    name = "assignment_analytics_agent"

    def run(self, payload: AssignmentAnalyticsInput) -> AssignmentAnalyticsOutput:
        subs = payload.submissions
        n = len(subs)

        if n == 0:
            return AssignmentAnalyticsOutput(
                assignment_title=payload.assignment_title, submission_count=0, average_score_pct=None,
                score_distribution=[], most_failed_category=None, category_failure_rates=[],
                plagiarism_flagged_pair_count=payload.plagiarism_flagged_pair_count,
            )

        pcts = [round(100 * s.score / s.total_points, 1) if s.total_points > 0 else 0.0 for s in subs]
        average = round(sum(pcts) / n, 1)

        buckets = []
        for lo, hi in _DISTRIBUTION_BUCKETS:
            count = sum(1 for p in pcts if lo <= p < hi)
            buckets.append(ScoreDistributionBucket(range_label=_bucket_label(lo, hi), count=count))

        category_fail_counts: dict[str, int] = defaultdict(int)
        for s in subs:
            for cat in s.failing_categories:
                category_fail_counts[cat] += 1

        category_rates = sorted(
            [
                CategoryFailureRate(category=cat, failure_count=count, failure_rate=round(count / n, 3))
                for cat, count in category_fail_counts.items()
            ],
            key=lambda c: -c.failure_count,
        )
        most_failed = category_rates[0].category if category_rates else None

        return AssignmentAnalyticsOutput(
            assignment_title=payload.assignment_title,
            submission_count=n,
            average_score_pct=average,
            score_distribution=buckets,
            most_failed_category=most_failed,
            category_failure_rates=category_rates,
            plagiarism_flagged_pair_count=payload.plagiarism_flagged_pair_count,
        )


class AssignmentPerformanceSummary(BaseModel):
    assignment_id: str
    title: str
    average_score_pct: float | None
    submission_count: int


class CourseAnalyticsInput(BaseModel):
    course_name: str
    assignment_summaries: list[AssignmentPerformanceSummary]
    total_plagiarism_flagged_pair_count: int


class CourseAnalyticsOutput(BaseModel):
    course_name: str
    assignment_count: int
    student_submission_count: int
    average_score_pct: float | None
    per_assignment_performance: list[AssignmentPerformanceSummary]
    weakest_assignment: str | None  # lowest average_score_pct, a concrete "where to focus review" signal
    total_plagiarism_flagged_pair_count: int


class CourseAnalyticsAgent(Agent[CourseAnalyticsInput, CourseAnalyticsOutput]):
    name = "course_analytics_agent"

    def run(self, payload: CourseAnalyticsInput) -> CourseAnalyticsOutput:
        graded = [a for a in payload.assignment_summaries if a.average_score_pct is not None]
        # Weighted by submission count, not a flat mean of per-assignment averages —
        # an assignment three students did shouldn't count the same as one thirty did.
        total_submissions = sum(a.submission_count for a in payload.assignment_summaries)
        if graded and total_submissions > 0:
            weighted_sum = sum(a.average_score_pct * a.submission_count for a in graded)
            overall_average = round(weighted_sum / sum(a.submission_count for a in graded), 1)
        else:
            overall_average = None

        weakest = min(graded, key=lambda a: a.average_score_pct).title if graded else None

        return CourseAnalyticsOutput(
            course_name=payload.course_name,
            assignment_count=len(payload.assignment_summaries),
            student_submission_count=total_submissions,
            average_score_pct=overall_average,
            per_assignment_performance=payload.assignment_summaries,
            weakest_assignment=weakest,
            total_plagiarism_flagged_pair_count=payload.total_plagiarism_flagged_pair_count,
        )

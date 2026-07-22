"""
Memory Agent — Phase 10.

Per the architecture doc's design: no separate memory *store* — short-term
memory is just the recent conversation (fetched from tutor_messages by
tutor_service.py), and long-term memory is recurring-mistake detection
across a student's past submissions (fetched from Feedback/ExecutionResult
by the same service layer). This agent is pure aggregation over what the
service hands it, same DB-agnostic pattern as every other agent — it
doesn't query anything itself.

"Teacher preferences" and "assignment history" (mentioned in the original
spec's Memory Agent description) aren't modeled here — there's no schema
concept of a teacher preference yet, and "assignment history" is already
directly queryable (a student's submissions table) rather than needing a
derived memory representation. Recurring mistakes is the one piece that
actually benefits from aggregation rather than a raw query, so that's
what this agent computes.
"""
from collections import Counter

from pydantic import BaseModel

from app.agents.base import Agent


class PastSubmissionOutcome(BaseModel):
    assignment_title: str
    failing_categories: list[str]


class MemoryInput(BaseModel):
    recent_messages: list[dict]  # [{"role": "user"|"tutor", "content": str}, ...], most recent last
    past_submissions: list[PastSubmissionOutcome]  # this student's history in this course, excluding current


class RecurringMistake(BaseModel):
    category: str
    occurrence_count: int


class MemoryOutput(BaseModel):
    short_term_summary: str
    recurring_mistakes: list[RecurringMistake]


MIN_OCCURRENCES_TO_FLAG = 2


class MemoryAgent(Agent[MemoryInput, MemoryOutput]):
    name = "memory_agent"

    def run(self, payload: MemoryInput) -> MemoryOutput:
        if payload.recent_messages:
            last = payload.recent_messages[-1]
            short_term_summary = f"Most recent message ({last['role']}): {last['content'][:200]}"
        else:
            short_term_summary = "No prior conversation."

        category_counts: Counter[str] = Counter()
        for sub in payload.past_submissions:
            # count each category once per submission, not once per failing test —
            # a student failing "edge_cases" three times on the SAME assignment is
            # one occurrence of that pattern, not three, when looking across assignments
            for category in set(sub.failing_categories):
                category_counts[category] += 1

        recurring = [
            RecurringMistake(category=cat, occurrence_count=count)
            for cat, count in category_counts.items()
            if count >= MIN_OCCURRENCES_TO_FLAG
        ]
        recurring.sort(key=lambda r: -r.occurrence_count)

        return MemoryOutput(short_term_summary=short_term_summary, recurring_mistakes=recurring)

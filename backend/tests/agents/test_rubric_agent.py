"""
agents/rubric_agent.py — mirrors the real normalization-math verification
from Phase 3 (see that phase's README section): weights that already sum
to 1.0 pass through unchanged, weights that don't get proportionally
rescaled, and the degenerate all-zero case is guarded rather than raising
a ZeroDivisionError.
"""
from app.agents.rubric_agent import DEFAULT_RUBRICS, _normalize
from app.db.models.assignment import AssignmentType


class TestNormalize:
    def test_weights_already_summing_to_one_are_unchanged(self):
        criteria = [{"name": "correctness", "weight": 0.5}, {"name": "efficiency", "weight": 0.5}]
        result = _normalize(criteria)
        assert sum(c["weight"] for c in result) == 1.0

    def test_weights_not_summing_to_one_are_rescaled_proportionally(self):
        criteria = [{"name": "correctness", "weight": 3}, {"name": "style", "weight": 1}]
        result = _normalize(criteria)
        assert sum(c["weight"] for c in result) == 1.0
        by_name = {c["name"]: c["weight"] for c in result}
        assert by_name["correctness"] == 0.75
        assert by_name["style"] == 0.25

    def test_degenerate_zero_total_falls_back_to_programming_default(self):
        result = _normalize([{"name": "x", "weight": 0}])
        assert result == DEFAULT_RUBRICS[AssignmentType.programming]

    def test_every_default_rubric_sums_to_one(self):
        # Every type-specific default is used both as the offline result AND as
        # the LLM's starting point — if one of these silently drifted from 1.0,
        # every rubric of that type would score against less than 100%.
        for assignment_type, criteria in DEFAULT_RUBRICS.items():
            total = round(sum(c["weight"] for c in criteria), 6)
            assert total == 1.0, f"{assignment_type} default rubric sums to {total}, not 1.0"

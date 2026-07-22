"""
agents/token_similarity_agent.py — mirrors the real shingling tests from
Phase 7: an exact copy scores 1.0, a copy with every identifier renamed
scores exactly 0.0 (not just "lower" — a precise, documented blind spot,
not a soft degradation), and a copy with identifiers unchanged but
reformatted/commented scores meaningfully high without being 1.0.
"""
from app.agents.token_similarity_agent import _jaccard, _shingles

ORIGINAL = """def add(a, b):
    result = a + b
    return result

def multiply(a, b):
    return a * b
"""

RENAMED_COPY = """def add(x, y):
    result = x + y
    return result

def multiply(x, y):
    return x * y
"""

REFORMATTED_SAME_NAMES = """
# my solution
def add(a,   b):
    result = a + b
    return result


def multiply(a, b):
    # multiply them
    return a * b
"""


class TestShingleSimilarity:
    def test_exact_copy_scores_one(self):
        assert _jaccard(_shingles(ORIGINAL), _shingles(ORIGINAL)) == 1.0

    def test_renamed_identifiers_score_exactly_zero(self):
        # The precise, documented blind spot — not "reduced," exactly zero.
        assert _jaccard(_shingles(ORIGINAL), _shingles(RENAMED_COPY)) == 0.0

    def test_reformatted_same_identifiers_scores_meaningfully_high(self):
        score = _jaccard(_shingles(ORIGINAL), _shingles(REFORMATTED_SAME_NAMES))
        assert 0.3 < score < 1.0

    def test_empty_content_has_zero_similarity_to_anything(self):
        assert _jaccard(_shingles(""), _shingles(ORIGINAL)) == 0.0

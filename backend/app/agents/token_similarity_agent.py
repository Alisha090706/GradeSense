"""
Token Similarity Agent — Phase 7.

AST comparison strips identifiers and literals, so it's excellent at
catching "restructured but logically identical" copies — including ones
where every variable was renamed — but says nothing about whether the
literal text was copied. Token shingling is the complementary case: it
operates on raw text, so it's blind to identifier-renamed copies (tested
directly while building this — renaming every variable in an otherwise
identical function drops Jaccard similarity to exactly 0.0, not just
"lower"; this technique provides no signal at all once identifiers
change), but it catches the more mundane real-world case AST can miss
nothing about: literal copy-paste with only whitespace, comments, or
formatting changed. Running both and reporting them under separate
`technique` values (not collapsed into one score) is the point — see
architecture doc's Similarity Agent section ("multiple techniques...
generate detailed reports").

Language-agnostic by construction (plain regex tokenization over raw
text) — this is also what finally makes similarity checking possible for
Java/C++/JS submissions, which similarity_agent.py's AST technique can't
touch (Python's `ast` module obviously doesn't parse Java).
"""
import itertools
import re
import statistics

from pydantic import BaseModel

from app.agents.base import Agent

SHINGLE_SIZE = 8
MIN_ABSOLUTE_THRESHOLD = 0.85
STD_DEVIATIONS_ABOVE_MEAN = 1.25
MAX_ADAPTIVE_THRESHOLD = 0.99

_TOKEN_RE = re.compile(r"\w+|[^\w\s]")


class TokenCandidate(BaseModel):
    student_id: str
    content: str
    ok: bool = True


class TokenSimilarityInput(BaseModel):
    submissions: list[TokenCandidate]


class TokenFlaggedPair(BaseModel):
    student_a: str
    student_b: str
    similarity: float


class TokenSimilarityOutput(BaseModel):
    technique: str = "token"
    threshold_used: float
    flagged_pairs: list[TokenFlaggedPair]
    note: str


def _shingles(content: str) -> set[str]:
    tokens = _TOKEN_RE.findall(content)
    if len(tokens) < SHINGLE_SIZE:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i:i + SHINGLE_SIZE]) for i in range(len(tokens) - SHINGLE_SIZE + 1)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


class TokenSimilarityAgent(Agent[TokenSimilarityInput, TokenSimilarityOutput]):
    name = "token_similarity_agent"

    def run(self, payload: TokenSimilarityInput) -> TokenSimilarityOutput:
        shingle_sets = {s.student_id: _shingles(s.content) for s in payload.submissions if s.ok}

        all_ratios = []
        scored_pairs = []
        for (id_a, sh_a), (id_b, sh_b) in itertools.combinations(shingle_sets.items(), 2):
            ratio = _jaccard(sh_a, sh_b)
            all_ratios.append(ratio)
            scored_pairs.append({"student_a": id_a, "student_b": id_b, "similarity": round(ratio, 3)})

        if len(all_ratios) >= 2:
            mean = statistics.mean(all_ratios)
            stdev = statistics.pstdev(all_ratios)
        else:
            mean = all_ratios[0] if all_ratios else 0.0
            stdev = 0.0
        threshold = min(MAX_ADAPTIVE_THRESHOLD, max(MIN_ABSOLUTE_THRESHOLD, mean + STD_DEVIATIONS_ABOVE_MEAN * stdev))

        pairs = [p for p in scored_pairs if p["similarity"] >= threshold]
        pairs.sort(key=lambda p: -p["similarity"])
        return TokenSimilarityOutput(
            threshold_used=round(threshold, 3),
            flagged_pairs=[TokenFlaggedPair(**p) for p in pairs],
            note=(
                f"{SHINGLE_SIZE}-token shingle Jaccard overlap on raw source text — catches "
                f"near-verbatim copies (including comments/formatting) but is fooled by "
                f"identifier renaming, unlike the AST technique. Threshold is adaptive "
                f"(class mean + 1.25 standard deviations, floor {MIN_ABSOLUTE_THRESHOLD:.0%}, "
                f"cap {MAX_ADAPTIVE_THRESHOLD:.0%})."
            ),
        )

"""
Similarity Agent — pydantic-wrapped port of the original similarity_agent.py.

Still AST-only in Phase 0 (matches the original prototype exactly). Phase 7
adds token-level (shingling/difflib over raw text) and embedding-based
(sentence-transformers cosine similarity) techniques alongside this one —
each will report its own `technique` field, matching the SimilarityReport
DB model's per-technique row design, rather than collapsing multiple
techniques into one opaque score.
"""
import ast
import difflib
import itertools
import statistics

from pydantic import BaseModel

from app.agents.base import Agent

MIN_ABSOLUTE_THRESHOLD = 0.93
STD_DEVIATIONS_ABOVE_MEAN = 1.25
MAX_ADAPTIVE_THRESHOLD = 0.99


class SimilarityCandidate(BaseModel):
    student_id: str
    path: str
    ok: bool


class SimilarityInput(BaseModel):
    submissions: list[SimilarityCandidate]


class FlaggedPair(BaseModel):
    student_a: str
    student_b: str
    similarity: float


class SimilarityOutput(BaseModel):
    threshold_used: float
    class_mean_similarity: float
    class_stdev_similarity: float
    flagged_pairs: list[FlaggedPair]
    unparseable: list[str]
    note: str


class _Normalizer(ast.NodeVisitor):
    def __init__(self):
        self.tokens = []

    def generic_visit(self, node):
        self.tokens.append(type(node).__name__)
        super().generic_visit(node)

    def visit_Name(self, node):
        self.tokens.append("NAME")

    def visit_Constant(self, node):
        self.tokens.append("CONST")

    def visit_arg(self, node):
        self.tokens.append("ARG")


def _normalize(path):
    with open(path) as f:
        source = f.read()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    norm = _Normalizer()
    norm.visit(tree)
    return norm.tokens


class SimilarityAgent(Agent[SimilarityInput, SimilarityOutput]):
    name = "similarity_agent"

    def run(self, payload: SimilarityInput) -> SimilarityOutput:
        normalized = {}
        unparseable = []
        for s in payload.submissions:
            if not s.ok:
                continue
            tokens = _normalize(s.path)
            if tokens is None:
                unparseable.append(s.student_id)
            else:
                normalized[s.student_id] = tokens

        all_ratios = []
        scored_pairs = []
        for (id_a, tok_a), (id_b, tok_b) in itertools.combinations(normalized.items(), 2):
            ratio = difflib.SequenceMatcher(None, tok_a, tok_b, autojunk=False).ratio()
            all_ratios.append(ratio)
            scored_pairs.append({"student_a": id_a, "student_b": id_b, "similarity": round(ratio, 3)})

        if len(all_ratios) >= 2:
            mean = statistics.mean(all_ratios)
            stdev = statistics.pstdev(all_ratios)
        else:
            mean = all_ratios[0] if all_ratios else 0.0
            stdev = 0.0
        adaptive_threshold = min(
            MAX_ADAPTIVE_THRESHOLD,
            max(MIN_ABSOLUTE_THRESHOLD, mean + STD_DEVIATIONS_ABOVE_MEAN * stdev),
        )

        pairs = [p for p in scored_pairs if p["similarity"] >= adaptive_threshold]
        pairs.sort(key=lambda p: -p["similarity"])
        return SimilarityOutput(
            threshold_used=round(adaptive_threshold, 3),
            class_mean_similarity=round(mean, 3),
            class_stdev_similarity=round(stdev, 3),
            flagged_pairs=[FlaggedPair(**p) for p in pairs],
            unparseable=unparseable,
            note=("Structural similarity only, based on AST shape with identifiers and literals "
                  "stripped. Threshold is adaptive (class mean + 1.25 standard deviations, floor "
                  "93%, cap 99%). This is a starting point for manual review, not evidence of "
                  "misconduct."),
        )

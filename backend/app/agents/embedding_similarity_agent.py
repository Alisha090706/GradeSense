"""
Embedding Similarity Agent — Phase 7.

The third similarity technique alongside AST (similarity_agent.py) and
token shingling (token_similarity_agent.py): embeds each submission's raw
source as text via sentence-transformers and flags pairs by cosine
similarity. This is the one technique that can catch genuinely
paraphrased/restructured copies that neither AST (same structure required)
nor token shingling (same literal text required) would — at the cost of
being the slowest and least precise of the three (semantic similarity is
inherently fuzzier than structural or textual match), which is exactly why
it's reported as its own `technique` value rather than blended into a
single score.

Testing note, stated plainly: sentence-transformers downloads a model
(~80MB for the default `all-MiniLM-L6-v2`) on first use, and this sandbox
has no network access — so unlike token_similarity_agent.py (pure stdlib,
genuinely tested above), this agent's embedding path has NOT been run
here. What IS tested: the cosine-similarity math itself, directly, with
synthetic vectors (see the test run while building this). The model-load
path is guarded to fail soft rather than crash — see `_load_model` below —
so a missing/undownloadable model degrades to "technique skipped, noted
in the report" rather than breaking the whole grading pipeline. Confirm
the actual embedding path once you have network access:
`python -c "from sentence_transformers import SentenceTransformer;
SentenceTransformer('all-MiniLM-L6-v2')"`.
Refactored in Phase 9 to use the shared agents/embedding_client.py rather
than its own duplicate model-loading logic, once retrieval_agent.py needed
the exact same lazy-load-and-degrade-gracefully behavior.
"""
import itertools
import statistics

from pydantic import BaseModel

from app.agents import embedding_client
from app.agents.base import Agent
from app.core.config import get_settings

MIN_ABSOLUTE_THRESHOLD = 0.90
STD_DEVIATIONS_ABOVE_MEAN = 1.25
MAX_ADAPTIVE_THRESHOLD = 0.995


class EmbeddingCandidate(BaseModel):
    student_id: str
    content: str
    ok: bool = True


class EmbeddingSimilarityInput(BaseModel):
    submissions: list[EmbeddingCandidate]


class EmbeddingFlaggedPair(BaseModel):
    student_a: str
    student_b: str
    similarity: float


class EmbeddingSimilarityOutput(BaseModel):
    technique: str = "embedding"
    skipped: bool = False
    threshold_used: float | None = None
    flagged_pairs: list[EmbeddingFlaggedPair] = []
    note: str


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class EmbeddingSimilarityAgent(Agent[EmbeddingSimilarityInput, EmbeddingSimilarityOutput]):
    name = "embedding_similarity_agent"

    def run(self, payload: EmbeddingSimilarityInput) -> EmbeddingSimilarityOutput:
        if not embedding_client.is_available():
            return EmbeddingSimilarityOutput(
                skipped=True,
                note=(
                    "Embedding similarity skipped — the sentence-transformers model "
                    "could not be loaded (no network access, or the package isn't "
                    "installed). Other similarity techniques still ran normally."
                ),
            )

        candidates = [s for s in payload.submissions if s.ok]
        if len(candidates) < 2:
            return EmbeddingSimilarityOutput(threshold_used=0.0, note="Fewer than 2 submissions to compare.")

        # Truncate to a reasonable length — this is a similarity signal on overall
        # approach/style, not a full-document diff; very long submissions would
        # otherwise dominate the model's context for no real benefit.
        texts = [c.content[:4000] for c in candidates]
        embeddings = embedding_client.embed_texts(texts)

        all_scores = []
        scored_pairs = []
        for (i, cand_a), (j, cand_b) in itertools.combinations(enumerate(candidates), 2):
            score = _cosine_similarity(list(embeddings[i]), list(embeddings[j]))
            all_scores.append(score)
            scored_pairs.append({"student_a": cand_a.student_id, "student_b": cand_b.student_id,
                                  "similarity": round(float(score), 3)})

        if len(all_scores) >= 2:
            mean = statistics.mean(all_scores)
            stdev = statistics.pstdev(all_scores)
        else:
            mean = all_scores[0] if all_scores else 0.0
            stdev = 0.0
        threshold = min(MAX_ADAPTIVE_THRESHOLD, max(MIN_ABSOLUTE_THRESHOLD, mean + STD_DEVIATIONS_ABOVE_MEAN * stdev))

        pairs = [p for p in scored_pairs if p["similarity"] >= threshold]
        pairs.sort(key=lambda p: -p["similarity"])
        return EmbeddingSimilarityOutput(
            threshold_used=round(threshold, 3),
            flagged_pairs=[EmbeddingFlaggedPair(**p) for p in pairs],
            note=(
                f"Semantic similarity via {get_settings().EMBEDDING_MODEL} sentence embeddings, "
                f"cosine distance. Catches paraphrased/restructured copies AST and token "
                f"techniques would miss, at the cost of being fuzzier — treat flagged pairs here "
                f"as a weaker signal than AST/token matches, worth a manual look rather than "
                f"treated as confirmation on their own."
            ),
        )

"""
Shared sentence-transformers embedding client — used by both
embedding_similarity_agent.py (Phase 7) and retrieval_agent.py (Phase 9).
Extracted here rather than duplicated, since both need the exact same
lazy-load-and-degrade-gracefully behavior: the model downloads on first
use (~80MB for the default all-MiniLM-L6-v2) and needs network for that
one-time download, so any code path that might run without network access
should degrade to "feature unavailable" rather than crash.

Testing note: as with embedding_similarity_agent.py before this refactor,
this sandbox has no network access, so the actual model-load path is
untested here — what's covered is everything downstream of "you already
have embeddings" (see retrieval_agent.py's chunking/storage logic, tested
independently of this module).
"""
from app.core.config import get_settings

_model = None
_model_load_failed = False


def is_available() -> bool:
    return load_model() is not None


def load_model():
    global _model, _model_load_failed
    if _model is not None or _model_load_failed:
        return _model
    try:
        from sentence_transformers import SentenceTransformer
        settings = get_settings()
        _model = SentenceTransformer(settings.EMBEDDING_MODEL)
    except Exception:
        _model_load_failed = True
        _model = None
    return _model


def embed_texts(texts: list[str]) -> list[list[float]] | None:
    """Returns None (not an exception) if the model isn't available — every
    caller treats that as "skip the embedding-dependent feature," matching the
    graceful-degradation pattern established in embedding_similarity_agent.py."""
    model = load_model()
    if model is None:
        return None
    return [list(v) for v in model.encode(texts)]

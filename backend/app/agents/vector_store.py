"""
ChromaDB wrapper — persistent local vector store, one collection per
course (per the architecture doc's RAG design). No Docker, per the
project's constraint — ChromaDB's persistent client just writes to a
local directory (settings.CHROMA_PERSIST_DIR), no server process needed.

Testing note: chromadb isn't installed in this sandbox (only what's
already present could be checked — see requirements.txt), so this module
is code-reviewed against ChromaDB's documented API, not run. The lazy
client pattern mirrors embedding_client.py's graceful degradation for
the same reason: RAG features should degrade to "unavailable" rather
than crash the app if chromadb isn't installed or its directory isn't
writable.
"""
from app.core.config import get_settings

_client = None
_client_init_failed = False


def is_available() -> bool:
    return _get_client() is not None


def _get_client():
    global _client, _client_init_failed
    if _client is not None or _client_init_failed:
        return _client
    try:
        import chromadb
        settings = get_settings()
        _client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    except Exception:
        _client_init_failed = True
        _client = None
    return _client


def _collection_name(course_id: str) -> str:
    return f"course_{course_id}"


def get_or_create_collection(course_id: str):
    client = _get_client()
    if client is None:
        return None
    return client.get_or_create_collection(name=_collection_name(course_id))


def upsert_chunks(
    course_id: str, document_id: str, filename: str, chunks: list[str], embeddings: list[list[float]],
) -> bool:
    """Returns False (not an exception) if the vector store isn't available —
    callers (retrieval_agent.py) treat that as "ingestion partially succeeded:
    the Document row and extracted text are saved, but nothing is searchable
    yet," which is a more honest state than pretending ingestion failed
    entirely when only the optional vector-store step did."""
    collection = get_or_create_collection(course_id)
    if collection is None:
        return False

    ids = [f"{document_id}:{i}" for i in range(len(chunks))]
    metadatas = [{"document_id": document_id, "filename": filename, "chunk_index": i} for i in range(len(chunks))]
    collection.upsert(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
    return True


def query(course_id: str, query_embedding: list[float], top_k: int = 5) -> list[dict]:
    """Returns [] if the vector store isn't available or the course has no
    ingested documents — never raises for "nothing to search," since an empty
    result is a completely normal state (e.g. before any teacher has uploaded
    anything), not an error."""
    collection = get_or_create_collection(course_id)
    if collection is None:
        return []
    if collection.count() == 0:
        return []

    result = collection.query(query_embeddings=[query_embedding], n_results=min(top_k, collection.count()))
    hits = []
    for doc, meta, distance in zip(result["documents"][0], result["metadatas"][0], result["distances"][0]):
        hits.append({"text": doc, "filename": meta.get("filename"), "document_id": meta.get("document_id"),
                     "distance": distance})
    return hits


def delete_document(course_id: str, document_id: str) -> None:
    collection = get_or_create_collection(course_id)
    if collection is None:
        return
    collection.delete(where={"document_id": document_id})

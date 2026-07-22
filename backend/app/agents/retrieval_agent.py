"""
Retrieval Agent — Phase 9.

Ties together document_extraction.py (txt/md/pdf -> text) ->
chunking.py (text -> overlapping chunks, genuinely tested) ->
embedding_client.py (chunks -> vectors, untestable here, no network) ->
vector_store.py (vectors -> ChromaDB, untestable here, not installed).

This is the ingestion half of RAG; the query half (embed a student's
question, retrieve top-k relevant chunks) is `retrieve` below, which
Phase 10's Tutor Agent will call — building it now since it's naturally
this agent's job ("how do I search what I ingested"), not the Tutor's.

Every failure mode degrades honestly rather than silently: unsupported
file types and unreadable PDFs raise clear errors before anything is
stored (see document_extraction.py); an unavailable embedding model or
vector store means ingestion partially succeeds (Document row + raw
extracted text saved) rather than the whole upload failing over an
optional downstream step — see `ingest`'s return value.
"""
from pydantic import BaseModel

from app.agents import chunking, document_extraction, embedding_client, vector_store
from app.agents.base import Agent
from app.agents.document_extraction import ExtractionError, UnsupportedFormatError


class IngestInput(BaseModel):
    course_id: str
    document_id: str
    filename: str
    content: bytes


class IngestOutput(BaseModel):
    chunk_count: int
    indexed: bool  # False if the embedding model or vector store was unavailable
    note: str


class RetrievalAgent(Agent[IngestInput, IngestOutput]):
    name = "retrieval_agent"

    def run(self, payload: IngestInput) -> IngestOutput:
        # Raises UnsupportedFormatError/ExtractionError straight through — the
        # caller (documents API route) is expected to turn these into a 400 with
        # the error's own message, which is already written for an end user.
        text = document_extraction.extract_text(payload.filename, payload.content)
        chunks = chunking.chunk_text(text)

        if not chunks:
            return IngestOutput(chunk_count=0, indexed=False, note="Document produced no text chunks.")

        embeddings = embedding_client.embed_texts(chunks)
        if embeddings is None:
            return IngestOutput(
                chunk_count=len(chunks), indexed=False,
                note=(
                    "Text extracted and chunked, but the embedding model is unavailable "
                    "(no network access, or sentence-transformers isn't installed) — "
                    "this document won't be searchable by the Tutor Agent until that's "
                    "resolved and it's re-ingested."
                ),
            )

        indexed = vector_store.upsert_chunks(payload.course_id, payload.document_id, payload.filename, chunks, embeddings)
        if not indexed:
            return IngestOutput(
                chunk_count=len(chunks), indexed=False,
                note="Text extracted, chunked, and embedded, but ChromaDB is unavailable — not stored for search.",
            )

        return IngestOutput(chunk_count=len(chunks), indexed=True, note="Ingested and indexed successfully.")


class RetrieveInput(BaseModel):
    course_id: str
    query: str
    top_k: int = 5


class RetrievedChunk(BaseModel):
    text: str
    filename: str | None
    document_id: str | None


class RetrieveOutput(BaseModel):
    chunks: list[RetrievedChunk]
    available: bool  # False if embeddings/vector store couldn't run this query at all
    note: str


def retrieve(payload: RetrieveInput) -> RetrieveOutput:
    """Not wrapped as an Agent subclass — it's a plain function rather than a
    pydantic-I/O Agent because Phase 10's Tutor Agent needs to call it as one
    step inside its own multi-step reasoning, not as a standalone pipeline
    stage the Orchestrator would invoke directly."""
    query_embeddings = embedding_client.embed_texts([payload.query])
    if query_embeddings is None:
        return RetrieveOutput(chunks=[], available=False, note="Embedding model unavailable — cannot search.")

    hits = vector_store.query(payload.course_id, query_embeddings[0], top_k=payload.top_k)
    return RetrieveOutput(
        chunks=[RetrievedChunk(text=h["text"], filename=h["filename"], document_id=h["document_id"]) for h in hits],
        available=True,
        note=f"{len(hits)} chunk(s) retrieved." if hits else "No matching content found for this course.",
    )

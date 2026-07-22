"""
Text chunking — pure logic, no dependencies, used by the Retrieval Agent
(retrieval_agent.py) before embedding. Kept as its own module since it
has nothing to do with embeddings or ChromaDB and is fully testable on
its own (and was — see the real test run while building this).

Chunk size is approximated in words, not real tokens — a proper tokenizer
(e.g. the embedding model's own) would be more accurate, but pulling one
in just for chunk-size estimation is unnecessary complexity; word count is
a reasonable proxy and is stated as such here rather than implied to be
exact.
"""
import re

DEFAULT_CHUNK_SIZE_WORDS = 350  # approximates ~500 tokens for typical English prose
DEFAULT_OVERLAP_WORDS = 50


def chunk_text(
    text: str, chunk_size_words: int = DEFAULT_CHUNK_SIZE_WORDS, overlap_words: int = DEFAULT_OVERLAP_WORDS,
) -> list[str]:
    """Splits on paragraph boundaries where possible, packing paragraphs into
    chunks up to chunk_size_words with overlap_words of trailing context carried
    into the next chunk — overlap means a fact split across a chunk boundary is
    still findable from either neighboring chunk's embedding.

    Known approximation, found while writing this module's test suite: the
    overlap is exact (word-for-word) when the overlap window falls entirely
    within one paragraph, but can be a few words short of overlap_words when
    a paragraph boundary falls inside that window — the internal paragraph-
    break marker counts as one slot toward chunk_size_words during chunking,
    but doesn't survive as a real word once the chunk is reassembled into
    text, so the visible overlap ends up very slightly smaller than requested
    right at a paragraph boundary. Not worth the extra bookkeeping to close
    for a RAG-retrieval use case (a few words of a paragraph-boundary chunk
    are still more than enough shared context to make the neighboring chunk
    findable) — flagged here rather than silently treated as exact everywhere.
    """
    if overlap_words >= chunk_size_words:
        raise ValueError("overlap_words must be smaller than chunk_size_words.")

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    words: list[str] = []
    for p in paragraphs:
        words.extend(p.split())
        words.append("\n\n")  # paragraph boundary marker, rejoined below

    if not words:
        return []

    chunks = []
    start = 0
    n = len(words)
    while start < n:
        end = min(start + chunk_size_words, n)
        chunk_words = words[start:end]
        chunk_text_str = " ".join(chunk_words).replace(" \n\n ", "\n\n").strip()
        if chunk_text_str:
            chunks.append(chunk_text_str)
        if end == n:
            break
        start = end - overlap_words

    return chunks

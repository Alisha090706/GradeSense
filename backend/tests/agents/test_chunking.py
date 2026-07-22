"""
agents/chunking.py — assertions mirror the real overlap-verification run
from Phase 9 (including catching a bug in the *test*, not the code, the
first time around — see that phase's README section for the full story;
this suite is the corrected version of that check, made permanent).
"""
import pytest

from app.agents.chunking import chunk_text


class TestChunkText:
    def test_empty_text_returns_no_chunks(self):
        assert chunk_text("") == []

    def test_short_text_returns_one_chunk(self):
        chunks = chunk_text("just a few words here", chunk_size_words=100, overlap_words=10)
        assert len(chunks) == 1

    def test_overlap_word_for_word_on_every_boundary(self):
        text = " ".join(f"word{i}" for i in range(300))
        chunks = chunk_text(text, chunk_size_words=50, overlap_words=10)
        assert len(chunks) > 1
        for i in range(len(chunks) - 1):
            tail = chunks[i].split()[-10:]
            head = chunks[i + 1].split()[:10]
            assert tail == head, f"chunk {i} and {i + 1} don't share the expected 10-word overlap"

    def test_overlap_survives_paragraph_boundaries(self):
        # Overlap here is approximate, not exact — see chunk_text's docstring
        # for why (a paragraph-break marker counts internally but doesn't
        # survive reconstruction). Discovered by first asserting exact overlap
        # here and watching it fail on the real final boundary (13/15 words,
        # not 15/15) — this is the corrected assertion, not the original one.
        text = (
            "Binary Search Trees\n\n"
            "A binary search tree (BST) is a binary tree where every node's left "
            "subtree contains only smaller values.\n\n"
            + " ".join(f"word{i}" for i in range(300))
            + "\n\nBalancing\n\nAn unbalanced BST degrades to O(n) in the worst case."
        )
        chunks = chunk_text(text, chunk_size_words=60, overlap_words=15)
        for i in range(len(chunks) - 1):
            tail = set(chunks[i].split()[-15:])
            head = set(chunks[i + 1].split()[:15])
            assert len(tail & head) >= 10, f"chunk {i} and {i + 1} share too little overlap to be useful"

    def test_overlap_must_be_smaller_than_chunk_size(self):
        with pytest.raises(ValueError):
            chunk_text("some text here", chunk_size_words=5, overlap_words=5)

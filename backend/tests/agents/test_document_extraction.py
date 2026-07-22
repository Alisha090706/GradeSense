"""
agents/document_extraction.py — mirrors the real reportlab-generated-PDF
verification from Phase 9 (see that phase's README section). Requires
reportlab as a test-only dependency to generate a real PDF fixture rather
than a hand-built byte string, which would only prove the parser accepts
whatever bytes it was told to accept.
"""
import pytest

from app.agents.document_extraction import ExtractionError, UnsupportedFormatError, extract_text

reportlab = pytest.importorskip("reportlab", reason="test-only dependency for generating a real PDF fixture")


def _make_pdf(pages: list[str]) -> bytes:
    import io
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    for line in pages:
        c.drawString(72, 700, line)
        c.showPage()
    c.save()
    return buf.getvalue()


class TestExtractText:
    def test_txt_extraction(self):
        assert extract_text("notes.txt", b"Plain text notes about recursion.") == "Plain text notes about recursion."

    def test_md_extraction(self):
        assert extract_text("notes.md", b"# Heading\n\nBody text.") == "# Heading\n\nBody text."

    def test_pdf_extraction_real_content(self):
        pdf_bytes = _make_pdf(["Lecture 4: Binary Search Trees", "Page 2: Balancing"])
        text = extract_text("lecture4.pdf", pdf_bytes)
        assert "Lecture 4: Binary Search Trees" in text
        assert "Page 2: Balancing" in text

    def test_unsupported_format_raises_with_clear_message(self):
        with pytest.raises(UnsupportedFormatError, match="pptx"):
            extract_text("slides.pptx", b"fake content")

    def test_blank_pdf_raises_extraction_error(self):
        blank_pdf = _make_pdf([])  # zero pages with any drawn text
        with pytest.raises(ExtractionError):
            extract_text("blank.pdf", blank_pdf)

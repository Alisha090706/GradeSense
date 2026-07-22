"""
Document text extraction — feeds chunking.py. Supports plain text/markdown
natively and PDF via pypdf. Slide decks (.pptx) and other formats
mentioned in the original spec ("lecture notes, PDFs, slides, lab
manuals") aren't handled yet — unsupported formats raise a clear
UnsupportedFormatError rather than silently returning empty text, so a
teacher gets a real error instead of a document that quietly never shows
up in Tutor answers.
"""
import io


class UnsupportedFormatError(ValueError):
    pass


class ExtractionError(ValueError):
    pass


def extract_text(filename: str, content: bytes) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext in ("txt", "md"):
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            return content.decode("utf-8", errors="replace")

    if ext == "pdf":
        return _extract_pdf(content)

    raise UnsupportedFormatError(
        f"Unsupported file type '.{ext}'. Supported: .txt, .md, .pdf. "
        f"(.pptx/.docx support is a natural follow-up, not implemented yet.)"
    )


def _extract_pdf(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ExtractionError("pypdf is not installed on this server — cannot extract PDF text.")

    try:
        reader = PdfReader(io.BytesIO(content))
    except Exception as e:
        raise ExtractionError(f"Could not open this file as a PDF: {e}")

    pages_text = []
    for page in reader.pages:
        pages_text.append(page.extract_text() or "")
    text = "\n\n".join(pages_text).strip()

    if not text:
        raise ExtractionError(
            "No extractable text found in this PDF — it may be a scanned image without "
            "OCR, which isn't supported yet."
        )
    return text

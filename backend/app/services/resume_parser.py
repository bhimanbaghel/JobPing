from io import BytesIO


class ResumeParseError(ValueError):
    pass


def extract_text_from_pdf_bytes(file_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - environment-specific
        raise ResumeParseError(
            "PDF parsing dependency missing. Install backend requirements."
        ) from exc

    try:
        reader = PdfReader(BytesIO(file_bytes))
    except Exception as exc:  # pragma: no cover - library-specific failures
        raise ResumeParseError("Could not read PDF resume.") from exc

    text_chunks = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
            text_chunks.append(page_text.strip())

    text = "\n".join(text_chunks).strip()
    if not text:
        raise ResumeParseError("Resume PDF appears empty or unreadable.")
    return text

"""Document parsing helpers for uploaded files."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path


class DocumentParseError(ValueError):
    """Raised when a document cannot produce searchable text."""


def parse_document(filename: str, content_type: str, payload: bytes) -> tuple[str, str]:
    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix in {"txt", "md"}:
        return _parse_text(payload), _content_type_for_suffix(suffix, content_type)
    if suffix == "pdf":
        return _parse_pdf(payload), "application/pdf"
    if suffix == "docx":
        return _parse_docx(payload), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    raise DocumentParseError("Only .txt, .md, .pdf and .docx documents are supported")


def _parse_text(payload: bytes) -> str:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DocumentParseError("Text documents must use UTF-8 encoding") from exc
    if not text.strip():
        raise DocumentParseError("Document has no searchable text")
    return text


def _parse_pdf(payload: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - only hit when runtime deps are missing
        raise DocumentParseError("Missing pypdf dependency; cannot parse PDF") from exc

    try:
        reader = PdfReader(BytesIO(payload))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except Exception as exc:  # noqa: BLE001
        raise DocumentParseError("PDF parse failed") from exc
    text = "\n\n".join(page for page in pages if page)
    if not text.strip():
        raise DocumentParseError("PDF has no searchable text; OCR is not supported yet")
    return text


def _parse_docx(payload: bytes) -> str:
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover - only hit when runtime deps are missing
        raise DocumentParseError("Missing python-docx dependency; cannot parse DOCX") from exc

    try:
        document = Document(BytesIO(payload))
    except Exception as exc:  # noqa: BLE001
        raise DocumentParseError("DOCX parse failed") from exc

    parts: list[str] = []
    parts.extend(paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip())
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    text = "\n\n".join(parts)
    if not text.strip():
        raise DocumentParseError("DOCX has no searchable text")
    return text


def _content_type_for_suffix(suffix: str, content_type: str) -> str:
    if suffix == "md":
        return content_type or "text/markdown"
    return content_type or "text/plain"

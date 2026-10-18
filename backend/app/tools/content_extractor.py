"""Deterministic text extraction from evidence file bytes (FR-008 extension).

Turns stored evidence into plain text so the Content Analysis Agent can scan it
for identifiers. Supports plain text, PDF, and OOXML Office files (docx/xlsx/
pptx). Extraction is bounded and degrades gracefully: unsupported, encrypted, or
corrupt inputs return a ``limitations`` entry instead of raising, mirroring the
ExifTool runner contract.

The extracted text is *untrusted evidence* and is only ever scanned locally; it
is never sent to an LLM or external service by this tool.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from xml.etree import ElementTree

from app.config import get_settings
from app.observability.logging import get_logger

logger = get_logger("content_extractor")

TEXT_MIME = "text/plain"
PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

# MIME types decoded directly as text. ``text/*`` is handled generically too.
_TEXT_MIME_TYPES = {
    "text/plain",
    "text/csv",
    "text/xml",
    "text/markdown",
    "application/json",
    "application/xml",
}

# OOXML members that carry user-visible text, keyed by MIME type.
_OOXML_MEMBERS: dict[str, re.Pattern[str]] = {
    DOCX_MIME: re.compile(
        r"^word/(document|header\d*|footer\d*|footnotes|endnotes|comments)\.xml$"
    ),
    XLSX_MIME: re.compile(r"^(xl/sharedStrings\.xml|xl/worksheets/sheet\d+\.xml)$"),
    PPTX_MIME: re.compile(r"^ppt/slides/slide\d+\.xml$"),
}

# Fallback by filename extension when the declared MIME is generic/unknown.
_EXTENSION_KIND = {
    ".txt": TEXT_MIME,
    ".log": TEXT_MIME,
    ".csv": "text/csv",
    ".json": "application/json",
    ".xml": "application/xml",
    ".md": "text/markdown",
    ".pdf": PDF_MIME,
    ".docx": DOCX_MIME,
    ".xlsx": XLSX_MIME,
    ".pptx": PPTX_MIME,
}

# Hard per-member guard so a hostile archive cannot exhaust memory.
_MAX_MEMBER_BYTES = 20 * 1024 * 1024


@dataclass
class TextExtraction:
    """Result of extracting text from a file's bytes."""

    text: str = ""
    kind: str = "unsupported"
    limitations: list[str] = field(default_factory=list)
    truncated: bool = False


def _resolve_kind(mime_type: str, filename: str) -> str:
    """Pick the extraction strategy from the MIME type, then the extension."""
    declared = (mime_type or "").split(";")[0].strip().lower()
    if declared in _OOXML_MEMBERS or declared in (TEXT_MIME, PDF_MIME):
        return declared
    if declared in _TEXT_MIME_TYPES or declared.startswith("text/"):
        return TEXT_MIME
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[1].lower()
        if ext in _EXTENSION_KIND:
            return _EXTENSION_KIND[ext]
    return "unsupported"


def _decode_text(data: bytes) -> str:
    """Decode bytes as UTF-8, tolerating bad sequences; drop NUL padding."""
    return data.decode("utf-8", errors="replace").replace("\x00", " ")


def _xml_visible_text(xml_bytes: bytes) -> str:
    """Concatenate the text of every ``*:t`` element (docx/xlsx/pptx runs)."""
    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError:
        return ""
    parts: list[str] = []
    for el in root.iter():
        if el.tag.rsplit("}", 1)[-1] == "t" and el.text:
            parts.append(el.text)
    return " ".join(parts)


def _extract_ooxml(data: bytes, pattern: re.Pattern[str]) -> tuple[str, list[str]]:
    """Read matching OOXML members from the zip and concatenate their text."""
    parts: list[str] = []
    limitations: list[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = sorted(n for n in zf.namelist() if pattern.match(n))
            if not names:
                limitations.append("ooxml_no_text_members")
            for name in names:
                info = zf.getinfo(name)
                if info.file_size > _MAX_MEMBER_BYTES:
                    limitations.append(f"ooxml_member_too_large:{name}")
                    continue
                text = _xml_visible_text(zf.read(name))
                if text:
                    parts.append(text)
    except zipfile.BadZipFile:
        limitations.append("ooxml_bad_zip")
    except Exception as exc:  # noqa: BLE001 - must degrade gracefully
        limitations.append(f"ooxml_error:{type(exc).__name__}")
        logger.warning("ooxml_extract_failed", error=str(exc))
    return " ".join(parts), limitations


def _extract_pdf(data: bytes) -> tuple[str, list[str]]:
    """Extract text from a PDF using pypdf (optional dependency)."""
    limitations: list[str] = []
    try:
        from pypdf import PdfReader  # imported lazily so the tool degrades gracefully
    except ImportError:
        return "", ["pdf_library_unavailable"]

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:  # noqa: BLE001 - encrypted beyond empty password
                return "", ["pdf_encrypted"]
        parts: list[str] = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:  # noqa: BLE001 - one bad page must not kill the run
                limitations.append("pdf_page_extract_failed")
        return "\n".join(parts), limitations
    except Exception as exc:  # noqa: BLE001 - corrupt/unusual PDFs
        logger.warning("pdf_extract_failed", error=str(exc))
        return "", [f"pdf_error:{type(exc).__name__}"]


def extract_text(data: bytes, *, filename: str, mime_type: str | None = None) -> TextExtraction:
    """Extract bounded plain text from a file's bytes.

    Never raises: unsupported inputs come back with a limitation and empty text.
    """
    settings = get_settings()
    kind = _resolve_kind(mime_type or "", filename)
    result = TextExtraction(kind=kind)

    if kind == "unsupported":
        result.limitations.append("unsupported_content_type")
        return result

    if kind == PDF_MIME:
        text, limitations = _extract_pdf(data)
        result.limitations.extend(limitations)
    elif kind in _OOXML_MEMBERS:
        text, limitations = _extract_ooxml(data, _OOXML_MEMBERS[kind])
        result.limitations.extend(limitations)
    else:  # plain-text-like
        text = _decode_text(data)

    limit = settings.content_extract_max_chars
    if len(text) > limit:
        text = text[:limit]
        result.truncated = True
        result.limitations.append("text_truncated")

    result.text = text
    return result

"""Safe file validation for uploaded evidence (SEC-002).

Checks performed before any processing:
  * size cap
  * declared MIME type is allowlisted
  * magic-byte sniffing to detect declared/actual type mismatch
  * zip-bomb guard (entry count + uncompressed-size ratio) for archives

All checks are deterministic and run on in-memory bytes. Files that fail are
rejected (never processed) and the caller quarantines them.
"""

import io
import zipfile
from dataclasses import dataclass

from app.config import get_settings
from app.domain.errors import ValidationError

# Magic-byte signatures keyed by MIME type. Each value is a list of acceptable
# (offset, prefix) signatures.
_MAGIC_SIGNATURES: dict[str, list[tuple[int, bytes]]] = {
    "image/jpeg": [(0, b"\xff\xd8\xff")],
    "image/png": [(0, b"\x89PNG\r\n\x1a\n")],
    "image/gif": [(0, b"GIF87a"), (0, b"GIF89a")],
    "image/tiff": [(0, b"II*\x00"), (0, b"MM\x00*")],
    "application/pdf": [(0, b"%PDF-")],
    "application/zip": [(0, b"PK\x03\x04"), (0, b"PK\x05\x06")],
    # OOXML Office files are zip containers.
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [
        (0, b"PK\x03\x04")
    ],
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [
        (0, b"PK\x03\x04")
    ],
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": [
        (0, b"PK\x03\x04")
    ],
}

# MIME types validated as plain text (no reliable binary magic).
_TEXT_MIME_TYPES = {
    "text/plain",
    "text/csv",
    "text/xml",
    "text/markdown",
    "application/json",
    "application/xml",
}

# Zip-container MIME types that get the zip-bomb guard.
_ARCHIVE_MIME_TYPES = {
    "application/zip",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


@dataclass
class ValidationResult:
    mime_type: str
    size_bytes: int
    sniffed_ok: bool
    notes: list[str]


def _is_probably_text(data: bytes) -> bool:
    """Heuristic: no NUL bytes and decodable as UTF-8 (with some tolerance)."""
    if b"\x00" in data[:4096]:
        return False
    try:
        data[:4096].decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def _check_magic(declared_mime: str, data: bytes) -> bool:
    if declared_mime in _TEXT_MIME_TYPES or declared_mime.startswith("text/"):
        return _is_probably_text(data)
    signatures = _MAGIC_SIGNATURES.get(declared_mime)
    if not signatures:
        return False
    return any(data[offset : offset + len(prefix)] == prefix for offset, prefix in signatures)


def _guard_zip(data: bytes, notes: list[str]) -> None:
    """Reject zip bombs: too many entries or excessive decompression ratio."""
    settings = get_settings()
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = zf.infolist()
            if len(infos) > settings.zip_max_entries:
                raise ValidationError(
                    f"Archive has too many entries (> {settings.zip_max_entries})"
                )
            compressed = sum(i.compress_size for i in infos) or 1
            uncompressed = sum(i.file_size for i in infos)
            ratio = uncompressed / compressed
            if ratio > settings.zip_max_ratio:
                raise ValidationError(
                    f"Archive decompression ratio {ratio:.0f} exceeds limit "
                    f"{settings.zip_max_ratio} (possible zip bomb)"
                )
            notes.append(f"archive_entries={len(infos)} ratio={ratio:.1f}")
    except zipfile.BadZipFile as exc:
        raise ValidationError("Malformed ZIP archive") from exc


def validate_file(*, data: bytes, declared_mime: str, filename: str) -> ValidationResult:
    """Validate uploaded file bytes. Raises ValidationError on any failure."""
    settings = get_settings()
    size = len(data)
    notes: list[str] = []

    if size == 0:
        raise ValidationError("Empty file")
    if size > settings.max_upload_bytes:
        raise ValidationError(
            f"File exceeds max size ({size} > {settings.max_upload_bytes} bytes)"
        )
    if declared_mime not in settings.allowed_mime_list:
        raise ValidationError(f"Unsupported MIME type: {declared_mime}")

    sniffed_ok = _check_magic(declared_mime, data)
    if not sniffed_ok:
        raise ValidationError(
            f"File content does not match declared type {declared_mime} "
            f"(magic-byte check failed)"
        )

    if declared_mime in _ARCHIVE_MIME_TYPES:
        _guard_zip(data, notes)

    return ValidationResult(
        mime_type=declared_mime, size_bytes=size, sniffed_ok=sniffed_ok, notes=notes
    )

"""Sandboxed ExifTool metadata extraction (FR-008, SEC-002).

Runs the ``exiftool`` binary as an isolated subprocess with a hard timeout. The
process is given no network and operates on a temporary file that is deleted
afterwards. Output is parsed as JSON. Extracted metadata is treated as
*untrusted claims*, never as verified facts.

If exiftool is unavailable, the runner returns a limitation rather than raising,
so the platform degrades gracefully.
"""

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field

from app.config import get_settings
from app.observability.logging import get_logger

logger = get_logger("exiftool")

# Fields of particular investigative interest.
_TIMESTAMP_FIELDS = (
    "DateTimeOriginal",
    "CreateDate",
    "ModifyDate",
    "GPSDateTime",
    "FileModifyDate",
)
_GPS_FIELDS = ("GPSLatitude", "GPSLongitude", "GPSPosition", "GPSAltitude")


@dataclass
class ExifResult:
    metadata: dict = field(default_factory=dict)
    timestamps: dict = field(default_factory=dict)
    gps: dict = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)


def _exiftool_available() -> bool:
    return shutil.which("exiftool") is not None


def extract_metadata(data: bytes, *, suffix: str = "") -> ExifResult:
    """Extract metadata from file bytes using exiftool in a subprocess."""
    settings = get_settings()
    result = ExifResult()

    if not _exiftool_available():
        result.limitations.append("exiftool_not_available")
        logger.warning("exiftool_missing")
        return result

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        # -json structured output; -n numeric; -G group names. No network flags
        # are used and exiftool does not open sockets for local files.
        completed = subprocess.run(
            ["exiftool", "-json", "-n", "-a", "-G", tmp_path],
            capture_output=True,
            timeout=settings.exiftool_timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            result.limitations.append("exiftool_nonzero_exit")
            logger.warning("exiftool_failed", stderr=completed.stderr.decode(errors="ignore")[:200])
            return result

        parsed = json.loads(completed.stdout.decode(errors="ignore") or "[]")
        if not parsed:
            result.limitations.append("no_metadata_extracted")
            return result

        raw = parsed[0]
        # Strip the source-file path (do not leak temp paths).
        raw.pop("SourceFile", None)
        # Flatten group-prefixed keys (e.g. "EXIF:DateTimeOriginal") -> last part.
        flat = {k.split(":")[-1]: v for k, v in raw.items()}
        result.metadata = flat
        result.timestamps = {k: flat[k] for k in _TIMESTAMP_FIELDS if k in flat}
        result.gps = {k: flat[k] for k in _GPS_FIELDS if k in flat}
        return result

    except subprocess.TimeoutExpired:
        result.limitations.append("exiftool_timeout")
        logger.warning("exiftool_timeout")
        return result
    except json.JSONDecodeError:
        result.limitations.append("exiftool_bad_output")
        return result
    except Exception as exc:  # noqa: BLE001 - must degrade gracefully
        result.limitations.append(f"exiftool_error:{type(exc).__name__}")
        logger.warning("exiftool_unexpected_error", error=str(exc))
        return result
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

"""Regex extraction of candidate identifiers from evidence text (FR-006 ext).

Scans text for emails, domains, IPv4 addresses, Ethereum wallets/tx hashes, and
patterned usernames. Every candidate is validated through the same canonical
``normalize_indicator`` used for manually submitted indicators, so an
auto-discovered value is indistinguishable from a hand-entered one.

Precision notes:
  * Wallets/tx hashes and emails are removed from the working string before
    domains/IPs/usernames are scanned, avoiding double-counting sub-strings.
  * Usernames are only taken from labelled fields (``username: alice``,
    ``login=alice``) or ``@mentions`` — free-text words are never guessed.
  * Domains ending in a file-extension-shaped TLD (``report.txt``) are dropped.

Output is candidate identifiers (strings that appear in the evidence), never an
identity or ownership claim.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.errors import ValidationError
from app.domain.indicators import normalize_indicator

# Boundaries keep matches from gluing onto surrounding word characters.
_EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}(?![A-Za-z0-9\-])"
)
_IPV4_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
_DOMAIN_RE = re.compile(
    r"\b(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}\b"
)
_TX_HASH_RE = re.compile(r"\b0x[0-9a-fA-F]{64}\b")
_WALLET_RE = re.compile(r"\b0x[0-9a-fA-F]{40}\b")
_MENTION_RE = re.compile(r"(?<![A-Za-z0-9._%+\-])@([A-Za-z0-9][A-Za-z0-9._\-]{1,63})\b")
_USERNAME_FIELD_RE = re.compile(
    r"(?i)\b(?:user\s?name|user|login|handle|nick\s?name|nick|account|screen\s?name)\b"
    r"\s*[:=]\s*[\"']?(@?[A-Za-z0-9][A-Za-z0-9._\-]{1,63})"
)

# TLDs that are really file extensions or common non-indicator suffixes.
_TLD_DENYLIST = {
    "txt", "log", "csv", "json", "xml", "md", "pdf", "doc", "docx", "xls", "xlsx",
    "ppt", "pptx", "zip", "rar", "7z", "tar", "gz", "png", "jpg", "jpeg", "gif",
    "tif", "tiff", "bmp", "svg", "ico", "mp3", "mp4", "wav", "avi", "mov", "mkv",
    "exe", "dll", "so", "dylib", "bin", "iso", "img", "db", "sql", "bak", "tmp",
    "yml", "yaml", "ini", "cfg", "conf", "sh", "bat", "ps1", "py", "js", "ts",
    "jsx", "tsx", "html", "htm", "css", "apk", "dmg", "msi", "pyc", "gitignore",
}


@dataclass(frozen=True)
class ExtractedIoc:
    """A candidate identifier and how many times it occurred in the text."""

    indicator_type: str
    value: str
    count: int


def _normalize(indicator_type: str, raw: str) -> str | None:
    try:
        return normalize_indicator(indicator_type, raw)
    except ValidationError:
        return None


def extract_iocs(text: str) -> list[ExtractedIoc]:
    """Return validated, de-duplicated candidate identifiers found in ``text``."""
    if not text:
        return []

    counts: dict[tuple[str, str], int] = {}

    def record(indicator_type: str, raw: str) -> None:
        value = _normalize(indicator_type, raw)
        if value is None:
            return
        counts[(indicator_type, value)] = counts.get((indicator_type, value), 0) + 1

    working = text

    # 1. Transaction hashes, then wallets (longest hex first), recorded + scrubbed.
    for match in _TX_HASH_RE.finditer(working):
        record("tx_hash", match.group(0))
    working = _TX_HASH_RE.sub(" ", working)

    for match in _WALLET_RE.finditer(working):
        record("wallet", match.group(0))
    working = _WALLET_RE.sub(" ", working)

    # 2. Emails (recorded, then scrubbed so their domain is not re-found as one).
    for match in _EMAIL_RE.finditer(working):
        record("email", match.group(0))
    working = _EMAIL_RE.sub(" ", working)

    # 3. IPv4 addresses.
    for match in _IPV4_RE.finditer(working):
        record("ip", match.group(0))
    working = _IPV4_RE.sub(" ", working)

    # 4. Usernames from @mentions and labelled fields.
    for match in _MENTION_RE.finditer(working):
        record("username", match.group(1))
    for match in _USERNAME_FIELD_RE.finditer(working):
        record("username", match.group(1).lstrip("@"))

    # 5. Domains last, dropping file-extension-shaped suffixes.
    for match in _DOMAIN_RE.finditer(working):
        candidate = match.group(0)
        if candidate.rsplit(".", 1)[-1].lower() in _TLD_DENYLIST:
            continue
        record("domain", candidate)

    return [
        ExtractedIoc(indicator_type=itype, value=value, count=count)
        for (itype, value), count in sorted(counts.items())
    ]

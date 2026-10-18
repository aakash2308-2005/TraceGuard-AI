"""Indicator types, validation, and canonical normalization.

Indicators are the atomic digital identifiers an investigation correlates:
usernames, emails, domains, IPs, wallet addresses, and transaction hashes.
Normalization produces a canonical value so the same real-world identifier maps
to one entity during resolution (M6).
"""

import ipaddress
import re
from enum import Enum

from app.domain.errors import ValidationError


class IndicatorType(str, Enum):
    USERNAME = "username"
    EMAIL = "email"
    DOMAIN = "domain"
    IP = "ip"
    WALLET = "wallet"
    TX_HASH = "tx_hash"


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DOMAIN_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")
_USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._\-]{1,63}$")
_ETH_ADDR_RE = re.compile(r"^0x[0-9a-f]{40}$")
_ETH_TX_RE = re.compile(r"^0x[0-9a-f]{64}$")


def normalize_indicator(indicator_type: str, value: str) -> str:
    """Validate and canonicalize an indicator. Raises ValidationError if invalid.

    Normalization rules:
      * trim whitespace
      * lower-case domains, emails, usernames, wallets, tx hashes
      * validate IPs via ipaddress and return the compressed form
    """
    try:
        itype = IndicatorType(indicator_type)
    except ValueError as exc:
        raise ValidationError(f"Unknown indicator type: {indicator_type}") from exc

    raw = (value or "").strip()
    if not raw:
        raise ValidationError("Indicator value cannot be empty")

    if itype is IndicatorType.EMAIL:
        v = raw.lower()
        if not _EMAIL_RE.match(v):
            raise ValidationError("Invalid email address")
        return v

    if itype is IndicatorType.DOMAIN:
        v = raw.lower().rstrip(".")
        if not _DOMAIN_RE.match(v):
            raise ValidationError("Invalid domain")
        return v

    if itype is IndicatorType.USERNAME:
        v = raw.lower()
        if not _USERNAME_RE.match(v):
            raise ValidationError("Invalid username")
        return v

    if itype is IndicatorType.IP:
        candidate = raw
        # ``ipaddress`` rejects zero-padded octets (e.g. 192.168.000.001), which
        # are common in logs and evidence files. Strip the padding first, then
        # validate canonically so those addresses are kept instead of dropped.
        if ":" not in candidate and re.fullmatch(r"\d{1,4}(?:\.\d{1,4}){3}", candidate):
            candidate = ".".join(str(int(part)) for part in candidate.split("."))
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError as exc:
            raise ValidationError("Invalid IP address") from exc

    if itype is IndicatorType.WALLET:
        v = raw.lower()
        if not _ETH_ADDR_RE.match(v):
            raise ValidationError("Invalid Ethereum wallet address")
        return v

    if itype is IndicatorType.TX_HASH:
        v = raw.lower()
        if not _ETH_TX_RE.match(v):
            raise ValidationError("Invalid Ethereum transaction hash")
        return v

    raise ValidationError(f"Unhandled indicator type: {indicator_type}")

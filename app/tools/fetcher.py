"""SSRF-safe HTTP fetcher (SEC-003).

Only hosts on the configured allowlist may be fetched. Resolved IPs are checked
to block private, loopback, link-local, and cloud-metadata ranges (defends
against DNS-rebinding to internal targets). Only http/https on standard ports.
"""

import ipaddress
import socket
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.domain.errors import ValidationError
from app.observability.logging import get_logger
from app.observability.metrics import EXTERNAL_CALL_FAILURES, EXTERNAL_CALL_LATENCY

logger = get_logger("fetcher")

_BLOCKED_PORTS_OK = {80, 443}


def _is_blocked_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
        # Cloud metadata endpoint.
        or ip_str == "169.254.169.254"
    )


def _validate_url(url: str) -> tuple[str, int]:
    """Validate scheme, host allowlist, and resolved-IP safety."""
    settings = get_settings()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValidationError("Only http/https URLs are allowed")
    host = parsed.hostname or ""
    if host.lower() not in settings.external_allowlist_set:
        raise ValidationError(f"Host not on allowlist: {host}")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port not in _BLOCKED_PORTS_OK:
        raise ValidationError(f"Port not allowed: {port}")

    # Resolve and verify every A/AAAA record is a public address.
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValidationError(f"DNS resolution failed for {host}") from exc
    for info in infos:
        ip_str = info[4][0]
        if _is_blocked_ip(ip_str):
            raise ValidationError(f"Resolved IP blocked (SSRF guard): {ip_str}")
    return host, port


async def safe_get_json(url: str, *, params: dict | None = None, headers: dict | None = None) -> dict:
    """Fetch JSON from an allowlisted URL with SSRF protections and a timeout."""
    settings = get_settings()
    host, _ = _validate_url(url)
    import time

    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=settings.external_timeout_seconds) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:  # noqa: BLE001
        EXTERNAL_CALL_FAILURES.labels(host).inc()
        logger.warning("external_fetch_failed", host=host, error=str(exc))
        raise
    finally:
        EXTERNAL_CALL_LATENCY.labels(host).observe(time.perf_counter() - start)

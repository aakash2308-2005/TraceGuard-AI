"""OSINT deterministic tools: RDAP/DNS and VirusTotal.

Mock-first: when ``OSINT_MODE=mock`` the tools return deterministic fixtures so
investigations run fully offline. Live mode calls real APIs through the
SSRF-safe fetcher. Every result records its source and retrieval timestamp.
"""

from datetime import datetime, timezone

from app.config import get_settings
from app.observability.logging import get_logger
from app.tools.fetcher import safe_get_json

logger = get_logger("osint_tools")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Deterministic fixtures keyed loosely by value so demo scenarios are stable.
def _mock_rdap(domain: str) -> dict:
    return {
        "source": "rdap_mock",
        "retrieved_at": _now(),
        "domain": domain,
        "registrar": "Example Registrar, Inc. (mock)",
        "created": "2021-03-14T00:00:00Z",
        "nameservers": ["ns1.example-mock.net", "ns2.example-mock.net"],
        "reliability_tier": "medium",
    }


def _mock_virustotal(indicator: str) -> dict:
    # Deterministic pseudo-reputation: everything benign in mock mode unless the
    # indicator contains the demo marker "malware".
    malicious = "malware" in indicator.lower()
    return {
        "source": "virustotal_mock",
        "retrieved_at": _now(),
        "indicator": indicator,
        "malicious_votes": 7 if malicious else 0,
        "harmless_votes": 0 if malicious else 60,
        "reputation": "malicious" if malicious else "harmless",
        "reliability_tier": "medium",
    }


async def rdap_lookup(domain: str) -> dict:
    """Look up domain registration via RDAP."""
    settings = get_settings()
    if settings.osint_mode == "mock":
        return _mock_rdap(domain)
    url = f"https://rdap.org/domain/{domain}"
    try:
        data = await safe_get_json(url)
        return {
            "source": "rdap",
            "retrieved_at": _now(),
            "domain": domain,
            "raw": data,
            "reliability_tier": "high",
        }
    except Exception as exc:  # noqa: BLE001 - caller records limitation
        logger.warning("rdap_failed", domain=domain, error=str(exc))
        return {"source": "rdap", "retrieved_at": _now(), "domain": domain, "error": str(exc)}


async def virustotal_lookup(indicator: str, *, kind: str) -> dict:
    """Query VirusTotal reputation for a domain/ip/url."""
    settings = get_settings()
    if settings.osint_mode == "mock":
        return _mock_virustotal(indicator)
    base = {"domain": "domains", "ip": "ip_addresses"}.get(kind, "domains")
    url = f"https://www.virustotal.com/api/v3/{base}/{indicator}"
    headers = {"x-apikey": settings.virustotal_api_key}
    try:
        data = await safe_get_json(url, headers=headers)
        return {
            "source": "virustotal",
            "retrieved_at": _now(),
            "indicator": indicator,
            "raw": data,
            "reliability_tier": "high",
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("virustotal_failed", indicator=indicator, error=str(exc))
        return {
            "source": "virustotal",
            "retrieved_at": _now(),
            "indicator": indicator,
            "error": str(exc),
        }

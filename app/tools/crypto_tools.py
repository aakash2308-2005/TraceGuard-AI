"""Crypto deterministic tools: Etherscan-compatible wallet/transaction reads.

Ethereum only (MVP). Mock-first: ``CRYPTO_MODE=mock`` returns deterministic
on-chain fixtures. Live mode calls Etherscan through the SSRF-safe fetcher.
All results record network, tx ids, timestamps, and source references.
"""

from datetime import datetime, timezone

from app.config import get_settings
from app.observability.logging import get_logger
from app.tools.fetcher import safe_get_json

logger = get_logger("crypto_tools")
_NETWORK = "ethereum"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mock_wallet_txns(address: str) -> dict:
    # Deterministic two-hop pattern for demo: address -> counterparty -> exchange.
    counterparty = "0x" + "cc" * 20
    exchange = "0x" + "ee" * 20
    return {
        "source": "etherscan_mock",
        "network": _NETWORK,
        "retrieved_at": _now(),
        "address": address,
        "transactions": [
            {
                "hash": "0x" + "a1" * 32,
                "from": address,
                "to": counterparty,
                "value_eth": 1.5,
                "timestamp": "2024-01-15T10:00:00Z",
            },
            {
                "hash": "0x" + "b2" * 32,
                "from": counterparty,
                "to": exchange,
                "value_eth": 1.4,
                "timestamp": "2024-01-15T12:30:00Z",
            },
        ],
        "reliability_tier": "high",
    }


async def wallet_transactions(address: str) -> dict:
    """Return public transaction history for an Ethereum address."""
    settings = get_settings()
    if settings.crypto_mode == "mock":
        return _mock_wallet_txns(address)
    url = settings.etherscan_base_url
    params = {
        "module": "account",
        "action": "txlist",
        "address": address,
        "sort": "asc",
        "apikey": settings.etherscan_api_key,
    }
    try:
        data = await safe_get_json(url, params=params)
        return {
            "source": "etherscan",
            "network": _NETWORK,
            "retrieved_at": _now(),
            "address": address,
            "raw": data,
            "reliability_tier": "high",
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("etherscan_failed", address=address, error=str(exc))
        return {
            "source": "etherscan",
            "network": _NETWORK,
            "retrieved_at": _now(),
            "address": address,
            "error": str(exc),
        }

"""IBM Z adapter port + real and mock implementations (design 2.12).

Business purpose: supplementary enterprise-grade anomaly/risk scoring that
corroborates (never replaces) the transparent, deterministic Confidence Engine.

Data exchanged: a derived, NON-SENSITIVE numeric feature vector plus an
investigation id. No raw evidence or PII is ever sent.

Hard constraints enforced here:
  * No fabricated IBM APIs/SDKs. The real adapter calls a configured HTTPS
    endpoint; if none is configured it refuses rather than pretending.
  * The mock adapter is explicitly labelled SIMULATED in every response.
  * Failures degrade gracefully: the caller proceeds without the Z score and
    records a limitation.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from functools import lru_cache

import httpx

from app.config import get_settings
from app.observability.logging import get_logger

logger = get_logger("ibmz")


class IBMZScore:
    """Result of an IBM Z scoring call.

    ``simulated`` is True for the mock adapter so the UI/report can label it
    unambiguously. ``available`` is False when scoring could not be obtained.
    """

    def __init__(
        self,
        *,
        score: float | None,
        simulated: bool,
        available: bool,
        detail: str,
        source: str,
    ) -> None:
        self.score = score
        self.simulated = simulated
        self.available = available
        self.detail = detail
        self.source = source

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "simulated": self.simulated,
            "available": self.available,
            "detail": self.detail,
            "source": self.source,
        }


class IBMZAdapter(ABC):
    """Abstract IBM Z scoring boundary."""

    mode: str = "abstract"

    @abstractmethod
    async def score(self, *, investigation_id: str, features: dict[str, float]) -> IBMZScore:
        """Return a supplementary risk score for a derived feature vector."""
        raise NotImplementedError

    @abstractmethod
    async def health(self) -> dict:
        """Report adapter availability for readiness checks."""
        raise NotImplementedError


class MockIBMZAdapter(IBMZAdapter):
    """Clearly-labelled SIMULATED scoring for offline development and demos.

    The score is a deterministic function of the feature vector so demos are
    reproducible. It is NOT a real IBM Z result and is always marked simulated.
    """

    mode = "mock"

    async def score(self, *, investigation_id: str, features: dict[str, float]) -> IBMZScore:
        # Deterministic pseudo-score derived from the feature vector hash, scaled
        # into [0,1]. Purely illustrative; never presented as a real Z result.
        material = ";".join(f"{k}={features[k]:.4f}" for k in sorted(features))
        digest = hashlib.sha256(material.encode()).hexdigest()
        pseudo = int(digest[:8], 16) / 0xFFFFFFFF
        # Nudge toward the deterministic feature signal so it is not pure noise.
        signal = features.get("corroboration", 0.0) * 0.5 + features.get(
            "source_independence", 0.0
        ) * 0.3
        score = round(min(1.0, 0.3 * pseudo + 0.7 * signal), 3)
        logger.info("ibmz_mock_score", investigation_id=investigation_id, score=score)
        return IBMZScore(
            score=score,
            simulated=True,
            available=True,
            detail="SIMULATED IBM Z scoring (mock adapter). Not a real z/OS result.",
            source="ibmz_mock",
        )

    async def health(self) -> dict:
        return {"mode": "mock", "available": True, "simulated": True}


class RealIBMZAdapter(IBMZAdapter):
    """Calls a configured ML for z/OS scoring endpoint over HTTPS.

    The exact request/response contract is confirmed against official IBM
    documentation before use. If no endpoint/token is configured, scoring is
    reported unavailable rather than fabricated.
    """

    mode = "real"

    def __init__(self) -> None:
        settings = get_settings()
        self._endpoint = settings.ibmz_endpoint
        self._token = settings.ibmz_api_token
        self._timeout = settings.ibmz_timeout_seconds

    async def score(self, *, investigation_id: str, features: dict[str, float]) -> IBMZScore:
        if not self._endpoint or not self._token:
            return IBMZScore(
                score=None,
                simulated=False,
                available=False,
                detail="IBMZ_MODE=real but IBMZ_ENDPOINT/IBMZ_API_TOKEN are not configured.",
                source="ibmz_real",
            )
        payload = {"investigation_id": investigation_id, "features": features}
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(self._endpoint, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            # Expected contract (confirm against ML for z/OS docs): {"score": float}
            score = float(data.get("score")) if data.get("score") is not None else None
            return IBMZScore(
                score=score,
                simulated=False,
                available=score is not None,
                detail="Live ML for z/OS scoring result.",
                source="ibmz_real",
            )
        except Exception as exc:  # noqa: BLE001 - graceful degradation (REL-002)
            logger.warning("ibmz_real_score_failed", error=str(exc))
            return IBMZScore(
                score=None,
                simulated=False,
                available=False,
                detail=f"IBM Z scoring unavailable: {type(exc).__name__}",
                source="ibmz_real",
            )

    async def health(self) -> dict:
        configured = bool(self._endpoint and self._token)
        return {"mode": "real", "available": configured, "simulated": False}


@lru_cache
def get_ibmz_adapter() -> IBMZAdapter:
    """Return the configured IBM Z adapter (cached)."""
    settings = get_settings()
    if settings.ibmz_mode == "real":
        return RealIBMZAdapter()
    return MockIBMZAdapter()

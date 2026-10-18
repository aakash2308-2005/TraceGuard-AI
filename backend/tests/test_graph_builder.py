"""Unit tests for the graph builder using a stub repository (no Neo4j)."""

import uuid

import pytest

from app.orchestration.graph_builder import build_graph
from app.orchestration.state import (
    ConfidenceResult,
    IndicatorRef,
    InvestigationState,
)


class StubGraphRepo:
    """Records calls instead of touching Neo4j."""

    def __init__(self) -> None:
        self.entities: list[dict] = []
        self.relationships: list[dict] = []

    async def upsert_entity(self, *, case_id, label, value, props=None):
        self.entities.append({"label": label, "value": value})

    async def upsert_relationship(
        self, *, case_id, from_label, from_value, to_label, to_value, rel_type, provenance
    ):
        self.relationships.append(
            {"from": from_value, "to": to_value, "rel": rel_type, "provenance": provenance}
        )


def _state(indicators, findings=None) -> InvestigationState:
    s = InvestigationState(
        investigation_id=str(uuid.uuid4()),
        case_id=str(uuid.uuid4()),
        started_by=str(uuid.uuid4()),
        indicators=indicators,
        findings=findings or [],
    )
    s.confidence = ConfidenceResult(score=0.5, band="moderate")
    return s


@pytest.mark.asyncio
async def test_indicators_become_entities():
    repo = StubGraphRepo()
    state = _state(
        [
            IndicatorRef(evidence_id="e1", indicator_type="domain", value="a.com"),
            IndicatorRef(evidence_id="e2", indicator_type="email", value="x@a.com"),
        ]
    )
    summary = await build_graph(state, repo)
    labels = {e["label"] for e in repo.entities}
    assert "Domain" in labels and "Email" in labels
    assert summary["nodes"] >= 2


@pytest.mark.asyncio
async def test_shared_ip_creates_edges_with_coocurrence_note():
    repo = StubGraphRepo()
    state = _state(
        [
            IndicatorRef(evidence_id="e1", indicator_type="ip", value="203.0.113.5"),
            IndicatorRef(evidence_id="e2", indicator_type="domain", value="a.com"),
            IndicatorRef(evidence_id="e3", indicator_type="username", value="shadow"),
        ]
    )
    await build_graph(state, repo)
    shares_ip = [r for r in repo.relationships if r["rel"] == "SHARES_IP"]
    assert len(shares_ip) == 2
    assert "co-occurrence" in shares_ip[0]["provenance"]["note"]


@pytest.mark.asyncio
async def test_wallet_relationship_is_associated_with_not_ownership():
    repo = StubGraphRepo()
    wallet = "0x" + "ab" * 20
    cp = "0x" + "cc" * 20
    state = _state(
        [IndicatorRef(evidence_id="e1", indicator_type="wallet", value=wallet)],
        findings=[
            {
                "claim_type": "possible_wallet_relationship",
                "agent_name": "crypto",
                "epistemic_status": "inference",
                "data": {"wallet": wallet, "counterparties": [cp]},
            }
        ],
    )
    await build_graph(state, repo)
    assoc = [r for r in repo.relationships if r["rel"] == "ASSOCIATED_WITH"]
    assert len(assoc) == 1
    # Provenance must preserve the inference status (not a fact).
    assert assoc[0]["provenance"]["epistemic_status"] == "inference"


@pytest.mark.asyncio
async def test_provenance_carries_confidence_band():
    repo = StubGraphRepo()
    wallet = "0x" + "ab" * 20
    state = _state(
        [IndicatorRef(evidence_id="e1", indicator_type="wallet", value=wallet)],
        findings=[
            {
                "claim_type": "possible_wallet_relationship",
                "agent_name": "crypto",
                "epistemic_status": "inference",
                "data": {"wallet": wallet, "counterparties": ["0x" + "cc" * 20]},
            }
        ],
    )
    await build_graph(state, repo)
    assoc = [r for r in repo.relationships if r["rel"] == "ASSOCIATED_WITH"]
    assert assoc[0]["provenance"]["confidence_band"] == "moderate"

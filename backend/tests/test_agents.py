"""Unit tests for OSINT, Crypto, and Defense agents in mock mode (no DB/objstore)."""

import uuid

import pytest

from app.agents.crypto_agent import CryptoAgent
from app.agents.defense_agent import DefenseAgent
from app.agents.osint_agent import OsintAgent
from app.orchestration.state import IndicatorRef, InvestigationState


def _state(indicators) -> InvestigationState:
    return InvestigationState(
        investigation_id=str(uuid.uuid4()),
        case_id=str(uuid.uuid4()),
        started_by=str(uuid.uuid4()),
        indicators=indicators,
        hypothesis="Indicators may belong to one actor.",
    )


@pytest.mark.asyncio
async def test_osint_agent_produces_cited_domain_fact():
    state = _state([IndicatorRef(evidence_id="e1", indicator_type="domain", value="example.com")])
    result = await OsintAgent().run(state)
    assert result.status == "completed"
    assert any(f["epistemic_status"] == "fact" for f in result.findings)
    assert result.source_refs  # cited sources present


@pytest.mark.asyncio
async def test_crypto_agent_separates_fact_from_inference():
    wallet = "0x" + "ab" * 20
    state = _state([IndicatorRef(evidence_id="e1", indicator_type="wallet", value=wallet)])
    result = await CryptoAgent().run(state)
    statuses = {f["epistemic_status"] for f in result.findings}
    assert "fact" in statuses  # on-chain transactions
    assert "inference" in statuses  # possible wallet relationship (not ownership)
    rel = [f for f in result.findings if f["claim_type"] == "possible_wallet_relationship"]
    assert "not evidence of shared ownership" in rel[0]["summary"]


@pytest.mark.asyncio
async def test_defense_agent_flags_shared_ip_alternative():
    # One IP + two other indicators triggers the shared-IP alternative heuristic.
    state = _state(
        [
            IndicatorRef(evidence_id="e1", indicator_type="ip", value="203.0.113.5"),
            IndicatorRef(evidence_id="e2", indicator_type="domain", value="a.com"),
            IndicatorRef(evidence_id="e3", indicator_type="email", value="x@a.com"),
        ]
    )
    result = await DefenseAgent().run(state)
    contradictions = result.extra["contradictions"]
    kinds = {c["kind"] for c in contradictions}
    assert "plausible_alternative" in kinds
    assert any("shared" in c["description"].lower() or "vpn" in c["description"].lower()
               for c in contradictions)


@pytest.mark.asyncio
async def test_defense_agent_never_empty_type():
    state = _state([IndicatorRef(evidence_id="e1", indicator_type="domain", value="a.com")])
    result = await DefenseAgent().run(state)
    for c in result.extra["contradictions"]:
        assert c["kind"] in {"verified_contradiction", "plausible_alternative", "open_question"}

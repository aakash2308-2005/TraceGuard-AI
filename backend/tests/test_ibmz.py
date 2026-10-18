"""Unit tests for the IBM Z adapter and feature extractor (mock mode, no network)."""

import uuid

import pytest

from app.integrations.ibmz.adapter import MockIBMZAdapter, RealIBMZAdapter
from app.integrations.ibmz.features import extract_features
from app.orchestration.state import AgentResult, IndicatorRef, InvestigationState


def _state() -> InvestigationState:
    s = InvestigationState(
        investigation_id=str(uuid.uuid4()),
        case_id=str(uuid.uuid4()),
        started_by=str(uuid.uuid4()),
        indicators=[IndicatorRef(evidence_id="e1", indicator_type="domain", value="a.com")],
        findings=[{"epistemic_status": "fact"}, {"epistemic_status": "inference"}],
    )
    s.agent_results["osint"] = AgentResult(
        agent_name="osint",
        status="completed",
        source_refs=[{"source_name": "rdap"}, {"source_name": "virustotal"}],
    )
    return s


def test_features_are_bounded_unit_interval():
    features = extract_features(_state())
    for name, value in features.items():
        assert 0.0 <= value <= 1.0, name
    assert "corroboration" in features
    assert "source_independence" in features


@pytest.mark.asyncio
async def test_mock_adapter_is_labelled_simulated():
    adapter = MockIBMZAdapter()
    features = extract_features(_state())
    result = await adapter.score(investigation_id="inv-1", features=features)
    assert result.simulated is True
    assert result.available is True
    assert "SIMULATED" in result.detail
    assert 0.0 <= result.score <= 1.0


@pytest.mark.asyncio
async def test_mock_adapter_is_deterministic():
    adapter = MockIBMZAdapter()
    features = extract_features(_state())
    r1 = await adapter.score(investigation_id="inv-1", features=features)
    r2 = await adapter.score(investigation_id="inv-1", features=features)
    assert r1.score == r2.score


@pytest.mark.asyncio
async def test_real_adapter_without_config_reports_unavailable():
    # In the test env IBMZ_ENDPOINT/TOKEN are unset, so real scoring must refuse
    # rather than fabricate a result.
    adapter = RealIBMZAdapter()
    result = await adapter.score(investigation_id="inv-1", features={"corroboration": 0.5})
    assert result.available is False
    assert result.simulated is False
    assert result.score is None


@pytest.mark.asyncio
async def test_confidence_attaches_ibmz_label():
    from app.agents.confidence_engine import compute_confidence

    state = _state()
    # Ensure a source ref + fact exist so we get a real score path.
    state.findings = [
        {"epistemic_status": "fact", "timestamp": "2024-01-01T00:00:00Z"},
    ]
    ibmz = {"score": 0.5, "simulated": True, "available": True, "detail": "x", "source": "ibmz_mock"}
    result = compute_confidence(state, ibmz_score=ibmz)
    assert result.ibmz is not None
    assert result.ibmz["simulated"] is True
    assert any("IBM Z" in lim for lim in result.limitations)

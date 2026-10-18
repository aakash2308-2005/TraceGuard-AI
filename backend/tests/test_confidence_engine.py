"""Unit tests for the deterministic Confidence Engine."""

import uuid

from app.agents.confidence_engine import compute_confidence
from app.orchestration.state import (
    AgentResult,
    ContradictionItem,
    InvestigationState,
)


def _state_with(findings, source_refs, contradictions=None) -> InvestigationState:
    state = InvestigationState(
        investigation_id=str(uuid.uuid4()),
        case_id=str(uuid.uuid4()),
        started_by=str(uuid.uuid4()),
        findings=findings,
    )
    state.agent_results["osint"] = AgentResult(
        agent_name="osint", status="completed", findings=findings, source_refs=source_refs
    )
    state.contradictions = contradictions or []
    return state


_FACT = {"epistemic_status": "fact", "claim_type": "registration", "timestamp": "2024-01-01T00:00:00Z"}
_SOURCE = {"source_name": "rdap", "reliability_tier": "high"}


def test_insufficient_without_facts():
    state = _state_with(
        findings=[{"epistemic_status": "inference"}], source_refs=[_SOURCE]
    )
    result = compute_confidence(state)
    assert result.band == "insufficient"
    assert result.score is None


def test_insufficient_without_sources():
    state = _state_with(findings=[_FACT], source_refs=[])
    result = compute_confidence(state)
    assert result.band == "insufficient"


def test_deterministic_same_inputs_same_score():
    state1 = _state_with(findings=[_FACT], source_refs=[_SOURCE])
    state2 = _state_with(findings=[_FACT], source_refs=[_SOURCE])
    r1 = compute_confidence(state1)
    r2 = compute_confidence(state2)
    assert r1.score == r2.score
    assert r1.band == r2.band


def test_verified_contradiction_lowers_score():
    base = _state_with(findings=[_FACT, _FACT], source_refs=[_SOURCE, _SOURCE])
    with_contra = _state_with(
        findings=[_FACT, _FACT],
        source_refs=[_SOURCE, _SOURCE],
        contradictions=[
            ContradictionItem(kind="verified_contradiction", description="x")
        ],
    )
    base_score = compute_confidence(base).score
    contra_score = compute_confidence(with_contra).score
    assert base_score is not None and contra_score is not None
    assert contra_score < base_score


def test_factors_are_explained():
    state = _state_with(findings=[_FACT], source_refs=[_SOURCE])
    result = compute_confidence(state)
    assert "source_reliability" in result.factors
    for factor in result.factors.values():
        assert "value" in factor and "weight" in factor and "rationale" in factor


def test_score_in_unit_interval():
    state = _state_with(findings=[_FACT, _FACT, _FACT], source_refs=[_SOURCE, _SOURCE])
    result = compute_confidence(state)
    assert 0.0 <= result.score <= 1.0

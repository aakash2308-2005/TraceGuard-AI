"""Unit tests for the report generator and citation validation (DB-free)."""

import uuid

import pytest

from app.agents.report_generator import ReportGenerator, _bucket_findings, validate_citations
from app.orchestration.state import (
    ConfidenceResult,
    ContradictionItem,
    InvestigationState,
)
from app.services.report_service import _content_hash


def _state() -> InvestigationState:
    s = InvestigationState(
        investigation_id=str(uuid.uuid4()),
        case_id=str(uuid.uuid4()),
        started_by=str(uuid.uuid4()),
        hypothesis="Possible single actor.",
        findings=[
            {
                "epistemic_status": "fact",
                "claim_type": "registration",
                "summary": "Domain registered",
                "agent_name": "osint",
                "timestamp": "2021-03-14T00:00:00Z",
                "data": {"source": "rdap_mock"},
            },
            {
                "epistemic_status": "inference",
                "claim_type": "possible_wallet_relationship",
                "summary": "Possible wallet association",
                "agent_name": "crypto",
            },
            {
                "epistemic_status": "fact",
                "claim_type": "x",
                "summary": "Uncited fact",
                "agent_name": "osint",
                # no source, no timestamp -> should be flagged
            },
        ],
    )
    s.contradictions = [
        ContradictionItem(kind="open_question", description="Ownership unverified"),
        ContradictionItem(kind="plausible_alternative", description="Shared VPN"),
    ]
    s.confidence = ConfidenceResult(score=0.5, band="moderate", limitations=["heuristic"])
    return s


def test_bucketing_separates_epistemic_status():
    buckets = _bucket_findings(_state())
    assert len(buckets["facts"]) == 2
    assert len(buckets["inferences"]) == 1


def test_citation_validator_flags_uncited_fact():
    buckets = _bucket_findings(_state())
    warnings = validate_citations(buckets)
    assert any("Uncited fact" in w for w in warnings)
    flagged = [f for f in buckets["facts"] if f.get("flagged_uncited")]
    assert len(flagged) == 1


@pytest.mark.asyncio
async def test_report_is_always_draft_with_sections():
    report = await ReportGenerator().generate(_state())
    assert report["status"] == "draft"
    assert "facts" in report and "inferences" in report and "hypotheses" in report
    assert report["contradictions"]
    assert any("review" in lim.lower() for lim in report["limitations"])
    assert "Ownership unverified" in report["open_questions"]


def test_content_hash_is_deterministic():
    content = {"a": 1, "b": [1, 2, 3]}
    assert _content_hash(content) == _content_hash({"b": [1, 2, 3], "a": 1})

"""Derive a non-sensitive numeric feature vector for IBM Z scoring.

Only aggregate, derived numbers leave the platform -- never raw indicators,
file contents, or PII. Each feature is bounded to [0,1] so the external model
receives a stable, privacy-preserving representation.
"""

from __future__ import annotations

from app.orchestration.state import InvestigationState


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def extract_features(state: InvestigationState) -> dict[str, float]:
    """Build the derived feature vector (all values in [0,1])."""
    findings = state.findings
    source_refs = [ref for r in state.agent_results.values() for ref in r.source_refs]
    distinct_sources = {ref.get("source_name") for ref in source_refs}

    fact_count = sum(1 for f in findings if f.get("epistemic_status") == "fact")
    verified_contradictions = sum(
        1 for c in state.contradictions if c.kind == "verified_contradiction"
    )

    return {
        "corroboration": _clamp(len(findings) / 6.0),
        "fact_ratio": _clamp(fact_count / max(len(findings), 1)),
        "source_independence": _clamp(len(distinct_sources) / max(len(source_refs), 1)),
        "contradiction_pressure": _clamp(verified_contradictions / 3.0),
        "indicator_breadth": _clamp(len(state.indicators) / 8.0),
        "limitation_pressure": _clamp(
            sum(len(r.limitations) for r in state.agent_results.values()) / 10.0
        ),
    }

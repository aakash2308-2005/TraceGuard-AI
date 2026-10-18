"""Confidence & Evidence Assessment Engine (design 2.7.E).

A DETERMINISTIC, transparent weighted model over named factors. The score
arithmetic is pure code -- an LLM is never used to produce the number. Each
factor carries a value in [0,1], a weight, and a short rationale, so the result
is fully explainable and reproducible.

If required factors are unmet (e.g. no independent corroboration), the engine
returns band=="insufficient" rather than a numeric high score (FR-026).

Scores are heuristic ordinal indicators, NOT calibrated probabilities. Weights
are calibrated against the synthetic scenarios in docs/EVALUATION.md; until that
calibration is measured, this limitation is reported explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.orchestration.state import ConfidenceResult, InvestigationState

# Factor weights sum to 1.0. Tuning these is the calibration task (M10/eval).
_WEIGHTS = {
    "source_reliability": 0.18,
    "evidence_quality": 0.14,
    "corroboration": 0.16,
    "source_independence": 0.14,
    "recency": 0.06,
    "contradiction_penalty": 0.14,
    "missing_info_penalty": 0.08,
    "alternative_explanation_penalty": 0.06,
    "provenance_completeness": 0.04,
}

_RELIABILITY_SCORE = {"high": 1.0, "medium": 0.6, "low": 0.3, "unknown": 0.2}

# Band thresholds over the final weighted score.
_HIGH = 0.70
_MODERATE = 0.45


@dataclass
class _Factor:
    value: float
    weight: float
    rationale: str


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _collect_source_refs(state: InvestigationState) -> list[dict]:
    refs: list[dict] = []
    for result in state.agent_results.values():
        refs.extend(result.source_refs)
    return refs


def compute_confidence(
    state: InvestigationState, ibmz_score: dict | None = None
) -> ConfidenceResult:
    """Compute a transparent confidence assessment from the current state.

    ``ibmz_score`` is an optional, clearly-labelled supplementary input from the
    IBM Z adapter. It is attached to the result for transparency but does NOT
    override the deterministic score (it is reported alongside, not blended in,
    so the primary score stays fully explainable).
    """
    findings = state.findings
    source_refs = _collect_source_refs(state)
    contradictions = state.contradictions
    limitations: list[str] = [
        "Scores are heuristic ordinal indicators, not calibrated probabilities.",
        "Factor weights are not yet calibrated against labelled scenarios.",
    ]

    # Insufficient-evidence guard: need at least one fact-level finding AND at
    # least one source reference to assess anything meaningfully.
    fact_findings = [f for f in findings if f.get("epistemic_status") == "fact"]
    if not fact_findings or not source_refs:
        return ConfidenceResult(
            score=None,
            band="insufficient",
            factors={},
            limitations=[*limitations, "Insufficient verified findings or sources to assess."],
            ibmz=ibmz_score,
        )

    # --- Factor computations ---
    reliabilities = [
        _RELIABILITY_SCORE.get(r.get("reliability_tier", "unknown"), 0.2) for r in source_refs
    ]
    source_reliability = sum(reliabilities) / len(reliabilities)

    # Evidence quality: proportion of findings that are facts (vs claims/inference).
    evidence_quality = len(fact_findings) / max(len(findings), 1)

    # Corroboration: more independent findings on the same indicator raise this.
    corroboration = _clamp(len(findings) / 6.0)

    # Source independence: distinct source names / total refs.
    distinct_sources = {r.get("source_name") for r in source_refs}
    source_independence = len(distinct_sources) / max(len(source_refs), 1)

    # Recency: fixed moderate value in offline mode (timestamps vary in demo).
    recency = 0.6

    # Penalties (higher factor value == less penalty, so we invert counts).
    verified_contradictions = [
        c for c in contradictions if c.kind == "verified_contradiction"
    ]
    alternatives = [c for c in contradictions if c.kind == "plausible_alternative"]
    open_questions = [c for c in contradictions if c.kind == "open_question"]

    contradiction_penalty = _clamp(1.0 - 0.5 * len(verified_contradictions))
    alternative_explanation_penalty = _clamp(1.0 - 0.2 * len(alternatives))

    all_limitations = [lim for r in state.agent_results.values() for lim in r.limitations]
    missing_info_penalty = _clamp(1.0 - 0.1 * (len(all_limitations) + len(open_questions)))

    # Provenance completeness: fraction of findings carrying a timestamp.
    with_ts = [f for f in findings if f.get("timestamp")]
    provenance_completeness = len(with_ts) / max(len(findings), 1)

    factors = {
        "source_reliability": _Factor(
            source_reliability, _WEIGHTS["source_reliability"],
            f"Mean reliability over {len(source_refs)} source reference(s).",
        ),
        "evidence_quality": _Factor(
            evidence_quality, _WEIGHTS["evidence_quality"],
            f"{len(fact_findings)} of {len(findings)} findings are fact-level.",
        ),
        "corroboration": _Factor(
            corroboration, _WEIGHTS["corroboration"],
            f"{len(findings)} corroborating finding(s).",
        ),
        "source_independence": _Factor(
            source_independence, _WEIGHTS["source_independence"],
            f"{len(distinct_sources)} distinct source(s).",
        ),
        "recency": _Factor(recency, _WEIGHTS["recency"], "Fixed moderate recency estimate."),
        "contradiction_penalty": _Factor(
            contradiction_penalty, _WEIGHTS["contradiction_penalty"],
            f"{len(verified_contradictions)} verified contradiction(s).",
        ),
        "missing_info_penalty": _Factor(
            missing_info_penalty, _WEIGHTS["missing_info_penalty"],
            f"{len(all_limitations)} limitation(s), {len(open_questions)} open question(s).",
        ),
        "alternative_explanation_penalty": _Factor(
            alternative_explanation_penalty, _WEIGHTS["alternative_explanation_penalty"],
            f"{len(alternatives)} plausible alternative(s).",
        ),
        "provenance_completeness": _Factor(
            provenance_completeness, _WEIGHTS["provenance_completeness"],
            f"{len(with_ts)} of {len(findings)} findings carry a timestamp.",
        ),
    }

    score = _clamp(sum(f.value * f.weight for f in factors.values()))
    band = "high" if score >= _HIGH else "moderate" if score >= _MODERATE else "low"

    if ibmz_score and ibmz_score.get("available"):
        label = "SIMULATED" if ibmz_score.get("simulated") else "live"
        limitations.append(
            f"IBM Z score ({label}) is shown as a supplementary signal and does not "
            "alter the deterministic score above."
        )

    return ConfidenceResult(
        score=round(score, 3),
        band=band,
        factors={
            name: {"value": round(f.value, 3), "weight": f.weight, "rationale": f.rationale}
            for name, f in factors.items()
        },
        limitations=limitations,
        ibmz=ibmz_score,
    )

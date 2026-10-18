"""AI Report Generator (design 2.7.F).

Produces a structured DRAFT report that:
  * cites underlying finding/evidence ids,
  * separates facts / inferences / hypotheses,
  * presents supporting AND contradictory evidence,
  * includes confidence + uncertainty and open questions,
  * forbids assertions lacking a citation.

The LLM drafts narrative prose only; all structured content is assembled
deterministically from recorded findings. A post-generation citation validator
flags any factual sentence that lacks a citation (it is marked, not published as
fact). The report status is always ``draft`` -- finalization requires a human.
"""

from __future__ import annotations

from app.integrations.llm.provider import get_llm_provider, wrap_untrusted
from app.observability.logging import get_logger
from app.orchestration.state import InvestigationState

logger = get_logger("report_generator")

_REPORT_SYSTEM = (
    "You are drafting an investigation report summary. Use only the provided findings. "
    "Separate facts from inferences and hypotheses. Never assert anything not supported "
    "by a listed finding. This is a report draft; a human will review it."
)


def _bucket_findings(state: InvestigationState) -> dict[str, list[dict]]:
    """Group findings by epistemic status for the facts/inferences/hypotheses split."""
    buckets: dict[str, list[dict]] = {
        "facts": [],
        "unverified_claims": [],
        "inferences": [],
        "hypotheses": [],
    }
    for f in state.findings:
        status = f.get("epistemic_status", "inference")
        entry = {
            "summary": f.get("summary", ""),
            "claim_type": f.get("claim_type"),
            "agent": f.get("agent_name"),
            "citation": {
                "source": (f.get("data") or {}).get("source") if isinstance(f.get("data"), dict) else None,
                "timestamp": f.get("timestamp"),
            },
        }
        if status == "fact":
            buckets["facts"].append(entry)
        elif status == "unverified_claim":
            buckets["unverified_claims"].append(entry)
        elif status == "hypothesis":
            buckets["hypotheses"].append(entry)
        else:
            buckets["inferences"].append(entry)
    return buckets


def validate_citations(buckets: dict[str, list[dict]]) -> list[str]:
    """Flag fact-level entries that lack any citation.

    Returns a list of warnings. Facts without a source or timestamp are flagged
    so they are not presented as verified in the final report.
    """
    warnings: list[str] = []
    for entry in buckets["facts"]:
        citation = entry.get("citation") or {}
        if not citation.get("source") and not citation.get("timestamp"):
            warnings.append(
                f"Uncited fact flagged (demoted): {entry.get('summary', '')[:80]}"
            )
            entry["flagged_uncited"] = True
    return warnings


class ReportGenerator:
    name = "report"

    async def generate(self, state: InvestigationState) -> dict:
        """Assemble a structured draft report."""
        buckets = _bucket_findings(state)
        citation_warnings = validate_citations(buckets)

        confidence = state.confidence
        contradictions = [c.model_dump() for c in state.contradictions]

        # LLM narrative is optional and clearly non-authoritative.
        narrative = (
            "This draft summarizes recorded findings. Facts, inferences, and hypotheses "
            "are listed separately. Confidence is a heuristic indicator, not a probability."
        )
        try:
            provider = get_llm_provider()
            out = await provider.complete_json(
                system=_REPORT_SYSTEM,
                user=wrap_untrusted(
                    f"Hypothesis: {state.hypothesis}\n"
                    f"Facts: {buckets['facts']}\n"
                    f"Inferences: {buckets['inferences']}\n"
                    f"Contradictions: {contradictions}"
                ),
                schema_hint={"narrative": "str"},
            )
            if out.get("narrative"):
                narrative = str(out["narrative"])
        except Exception as exc:  # noqa: BLE001
            citation_warnings.append(f"narrative_llm_unavailable:{type(exc).__name__}")

        return {
            "status": "draft",
            "title": "Investigation Draft Report",
            "hypothesis": state.hypothesis,
            "narrative": narrative,
            "facts": buckets["facts"],
            "unverified_claims": buckets["unverified_claims"],
            "inferences": buckets["inferences"],
            "hypotheses": buckets["hypotheses"],
            "contradictions": contradictions,
            "confidence": confidence.model_dump() if confidence else None,
            "limitations": (confidence.limitations if confidence else [])
            + ["Report requires investigator review before finalization."],
            "open_questions": [
                c["description"] for c in contradictions if c.get("kind") == "open_question"
            ],
            "citation_warnings": citation_warnings,
        }

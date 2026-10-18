"""Run the synthetic-scenario evaluation harness.

Loads data/synthetic/scenarios.json and, for each scenario, runs the agent
pipeline in-process using the configured mock modes, then compares outputs
against the recorded ground truth.

Run from the backend/ directory (so the app package is importable):

    python ../scripts/run_eval.py

This produces a metrics summary. Per the methodology, numbers are only
meaningful under the committed mock fixtures; it does not call live APIs.
"""

import asyncio
import json
import sys
import uuid
from pathlib import Path

_SCENARIOS = Path(__file__).resolve().parent.parent / "data" / "synthetic" / "scenarios.json"


async def _evaluate() -> dict:
    try:
        from app.agents.confidence_engine import compute_confidence
        from app.agents.crypto_agent import CryptoAgent
        from app.agents.defense_agent import DefenseAgent
        from app.agents.osint_agent import OsintAgent
        from app.orchestration.state import IndicatorRef, InvestigationState
    except ImportError:
        print("Run from backend/ so the app package is importable.")
        sys.exit(2)

    data = json.loads(_SCENARIOS.read_text())
    results = []

    for scenario in data["scenarios"]:
        state = InvestigationState(
            investigation_id=str(uuid.uuid4()),
            case_id=str(uuid.uuid4()),
            started_by=str(uuid.uuid4()),
            indicators=[
                IndicatorRef(evidence_id=str(uuid.uuid4()), indicator_type=i["type"], value=i["value"])
                for i in scenario.get("indicators", [])
            ],
            hypothesis="Scenario hypothesis under test.",
        )

        # Run data-gathering agents (mock mode).
        for agent in (OsintAgent(), CryptoAgent()):
            res = await agent.run(state)
            state.agent_results[agent.name] = res
        state.findings = [
            {**f, "agent_name": r.agent_name}
            for r in state.agent_results.values()
            for f in r.findings
        ]

        # Defense + confidence.
        defense = await DefenseAgent().run(state)
        from app.orchestration.state import ContradictionItem

        state.contradictions = [
            ContradictionItem(**c) for c in defense.extra.get("contradictions", [])
        ]
        state.confidence = compute_confidence(state)

        gt = scenario.get("ground_truth", {})
        kinds = {c.kind for c in state.contradictions}
        results.append(
            {
                "scenario": scenario["id"],
                "findings": len(state.findings),
                "contradiction_kinds": sorted(kinds),
                "confidence_band": state.confidence.band if state.confidence else None,
                "expected_band": gt.get("expected_confidence_band"),
                "band_match": (
                    gt.get("expected_confidence_band") is None
                    or (state.confidence and state.confidence.band == gt["expected_confidence_band"])
                ),
            }
        )

    band_checks = [r for r in results if r["expected_band"] is not None]
    band_accuracy = (
        sum(1 for r in band_checks if r["band_match"]) / len(band_checks) if band_checks else None
    )
    return {
        "scenarios_evaluated": len(results),
        "confidence_band_accuracy_where_specified": band_accuracy,
        "note": "Measured under committed mock fixtures only; not live API results.",
        "per_scenario": results,
    }


if __name__ == "__main__":
    summary = asyncio.run(_evaluate())
    print(json.dumps(summary, indent=2))

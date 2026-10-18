"""OSINT Agent: investigates indicators via authorized sources.

Resolves domains/IPs via RDAP and checks reputation via VirusTotal (mock-first).
Produces normalized findings with explicit epistemic status and cited sources.
The LLM is used only to synthesize a human-readable summary; all facts come from
deterministic tools.
"""

from app.agents.base import Agent
from app.integrations.llm.provider import get_llm_provider
from app.observability.logging import get_logger
from app.orchestration.state import AgentResult, InvestigationState
from app.tools.osint_tools import rdap_lookup, virustotal_lookup

logger = get_logger("osint_agent")

_OSINT_SYSTEM = (
    "You are an OSINT synthesis assistant. Given structured lookup results, write a "
    "concise, hedged summary. Do not assert ownership or identity. This is OSINT synthesis."
)


class OsintAgent(Agent):
    name = "osint"

    async def run(self, state: InvestigationState) -> AgentResult:
        findings: list[dict] = []
        source_refs: list[dict] = []
        limitations: list[str] = []

        for ind in state.indicators:
            if ind.indicator_type == "domain":
                rdap = await rdap_lookup(ind.value)
                if "error" in rdap:
                    limitations.append(f"rdap_failed:{ind.value}")
                else:
                    findings.append(
                        {
                            "summary": f"Domain {ind.value} registration data retrieved.",
                            "epistemic_status": "fact",
                            "claim_type": "registration",
                            "indicator": ind.value,
                            "data": rdap,
                            "timestamp": rdap.get("created"),
                        }
                    )
                    source_refs.append(
                        {
                            "source_name": rdap.get("source", "rdap"),
                            "url": None,
                            "retrieved_at": rdap.get("retrieved_at"),
                            "reliability_tier": rdap.get("reliability_tier", "medium"),
                        }
                    )

            if ind.indicator_type in ("domain", "ip"):
                vt = await virustotal_lookup(ind.value, kind=ind.indicator_type)
                if "error" in vt:
                    limitations.append(f"virustotal_failed:{ind.value}")
                else:
                    reputation = vt.get("reputation", "unknown")
                    findings.append(
                        {
                            "summary": f"Reputation for {ind.value}: {reputation}.",
                            "epistemic_status": "unverified_claim",
                            "claim_type": "reputation",
                            "indicator": ind.value,
                            "data": vt,
                            "timestamp": vt.get("retrieved_at"),
                        }
                    )
                    source_refs.append(
                        {
                            "source_name": vt.get("source", "virustotal"),
                            "url": None,
                            "retrieved_at": vt.get("retrieved_at"),
                            "reliability_tier": vt.get("reliability_tier", "medium"),
                        }
                    )

        if not state.indicators:
            limitations.append("no_indicators_to_investigate")

        # LLM synthesis is best-effort and never blocks fact findings.
        try:
            provider = get_llm_provider()
            await provider.complete_json(
                system=_OSINT_SYSTEM,
                user=f"Lookup results: {findings}",
                schema_hint={"summary": "str", "possible_relationships": "list"},
            )
        except Exception as exc:  # noqa: BLE001
            limitations.append(f"osint_synthesis_unavailable:{type(exc).__name__}")

        return AgentResult(
            agent_name=self.name,
            status="completed",
            findings=findings,
            source_refs=source_refs,
            limitations=limitations,
        )

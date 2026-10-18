"""Defense Agent (primary differentiator, design 2.7.D).

Actively searches for evidence contradicting the current hypothesis, generates
alternative explanations, and flags missing evidence and weak assumptions. It
must NOT invent contradictions. Each item is typed as:
  * verified_contradiction - backed by an observed fact in the findings
  * plausible_alternative  - a reasonable alternative explanation
  * open_question          - unresolved gap requiring a further check

Deterministic heuristics catch classic false-lead patterns (shared IP, VPN/Tor,
coincidental association). The LLM adds qualitative alternatives but its output
is constrained to the three types and never promoted to a verified contradiction.
"""

from app.agents.base import Agent
from app.integrations.llm.provider import get_llm_provider, wrap_untrusted
from app.observability.logging import get_logger
from app.orchestration.state import AgentResult, ContradictionItem, InvestigationState

logger = get_logger("defense_agent")

_DEFENSE_SYSTEM = (
    "You are the Defense Agent in a cybercrime investigation. Your job is defense: "
    "challenge the hypothesis. Propose alternative explanations and missing evidence. "
    "Never fabricate facts. Only describe plausible alternatives and open questions."
)

# IP-reputation-ish markers that commonly produce coincidental associations.
_SHARED_INFRA_HINTS = ("vpn", "tor", "proxy", "nat", "shared", "exit node")


class DefenseAgent(Agent):
    name = "defense"

    async def run(self, state: InvestigationState) -> AgentResult:
        contradictions: list[ContradictionItem] = []
        limitations: list[str] = []

        # 1. Deterministic heuristic: multiple indicators sharing one IP is a
        #    classic coincidence source -> plausible alternative, not proof.
        ip_findings = [
            f for f in state.findings if f.get("claim_type") in ("reputation", "registration")
        ]
        ips = [i.value for i in state.indicators if i.indicator_type == "ip"]
        if len(ips) == 1 and len([i for i in state.indicators if i.indicator_type != "ip"]) >= 2:
            contradictions.append(
                ContradictionItem(
                    kind="plausible_alternative",
                    description=(
                        "Multiple indicators are linked through a single shared IP address. "
                        "A shared VPN/NAT/proxy exit node could explain this without a common actor."
                    ),
                    basis="Shared-IP co-occurrence among otherwise-independent indicators.",
                    refs={"shared_ip": ips[0]},
                )
            )

        # 2. Wallet association must not be read as ownership.
        if any(f.get("claim_type") == "possible_wallet_relationship" for f in state.findings):
            contradictions.append(
                ContradictionItem(
                    kind="open_question",
                    description=(
                        "On-chain counterparty relationships were observed. These do not establish "
                        "wallet ownership or identity; off-chain attribution is unverified."
                    ),
                    basis="On-chain association without off-chain identity confirmation.",
                )
            )

        # 3. Low-reliability or missing corroboration -> open question.
        has_fact = any(f.get("epistemic_status") == "fact" for f in state.findings)
        if not has_fact:
            contradictions.append(
                ContradictionItem(
                    kind="open_question",
                    description="No fact-level findings were established; the hypothesis rests on "
                    "unverified claims and inferences.",
                    basis="Absence of verified facts in current findings.",
                )
            )

        # 4. Metadata-only timestamps can be forged -> weak assumption.
        if any(f.get("claim_type") == "file_metadata" for f in state.findings):
            contradictions.append(
                ContradictionItem(
                    kind="open_question",
                    description="File metadata (timestamps/GPS) are self-reported and can be "
                    "altered; they are not independently verified facts.",
                    basis="Metadata claims are not corroborated by an independent source.",
                )
            )

        # 5. LLM qualitative alternatives (constrained, best-effort).
        try:
            provider = get_llm_provider()
            out = await provider.complete_json(
                system=_DEFENSE_SYSTEM,
                user=wrap_untrusted(
                    f"Hypothesis: {state.hypothesis}\nFindings: {state.findings}"
                ),
                schema_hint={
                    "contradictions": "list",
                    "alternative_explanations": "list",
                    "missing_evidence": "list",
                    "weak_assumptions": "list",
                    "recommended_checks": "list",
                },
            )
            for alt in out.get("alternative_explanations", []):
                contradictions.append(
                    ContradictionItem(kind="plausible_alternative", description=str(alt))
                )
            for miss in out.get("missing_evidence", []):
                contradictions.append(ContradictionItem(kind="open_question", description=str(miss)))
        except Exception as exc:  # noqa: BLE001
            limitations.append(f"defense_llm_unavailable:{type(exc).__name__}")

        if not contradictions:
            limitations.append("no_contradictions_identified")

        return AgentResult(
            agent_name=self.name,
            status="completed",
            findings=[],
            limitations=limitations,
            extra={"contradictions": [c.model_dump() for c in contradictions]},
        )

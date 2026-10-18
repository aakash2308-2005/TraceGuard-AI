"""Crypto Agent: analyzes public Ethereum transactions and wallet histories.

Identifies transaction patterns and *possible* wallet relationships. Clearly
separates observable on-chain facts from inferred attribution. A wallet
association is never stated as proof of ownership or criminal activity.
"""

from app.agents.base import Agent
from app.observability.logging import get_logger
from app.orchestration.state import AgentResult, InvestigationState
from app.tools.crypto_tools import wallet_transactions

logger = get_logger("crypto_agent")


class CryptoAgent(Agent):
    name = "crypto"

    async def run(self, state: InvestigationState) -> AgentResult:
        findings: list[dict] = []
        source_refs: list[dict] = []
        limitations: list[str] = []

        wallets = [i for i in state.indicators if i.indicator_type == "wallet"]
        if not wallets:
            limitations.append("no_wallets_to_analyze")

        for w in wallets:
            result = await wallet_transactions(w.value)
            if "error" in result:
                limitations.append(f"etherscan_failed:{w.value}")
                continue

            txns = result.get("transactions") or result.get("raw", {}).get("result", [])
            # On-chain facts: each transaction observed.
            for tx in txns if isinstance(txns, list) else []:
                findings.append(
                    {
                        "summary": f"On-chain transaction {tx.get('hash', '')[:12]}… observed.",
                        "epistemic_status": "fact",
                        "claim_type": "transaction",
                        "network": result.get("network", "ethereum"),
                        "data": tx,
                        "timestamp": tx.get("timestamp"),
                    }
                )

            # Inferred attribution: a *possible* relationship, never ownership.
            counterparties = {
                tx.get("to") for tx in txns if isinstance(txns, list) and tx.get("to")
            }
            counterparties.discard(w.value)
            if counterparties:
                findings.append(
                    {
                        "summary": (
                            f"Wallet {w.value[:10]}… transacted with "
                            f"{len(counterparties)} counterpart address(es). This is a "
                            "possible association, not evidence of shared ownership."
                        ),
                        "epistemic_status": "inference",
                        "claim_type": "possible_wallet_relationship",
                        "data": {"wallet": w.value, "counterparties": list(counterparties)},
                        "timestamp": result.get("retrieved_at"),
                    }
                )

            source_refs.append(
                {
                    "source_name": result.get("source", "etherscan"),
                    "url": None,
                    "retrieved_at": result.get("retrieved_at"),
                    "reliability_tier": result.get("reliability_tier", "high"),
                }
            )

        return AgentResult(
            agent_name=self.name,
            status="completed",
            findings=findings,
            source_refs=source_refs,
            limitations=limitations,
        )

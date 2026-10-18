"""Translate investigation state into a provenance-aware Neo4j graph.

Entity normalization: each indicator becomes one case-scoped node. Relationships
are derived from agent findings and carry provenance (source, retrieved_at,
confidence_band). Two connected entities are NEVER merged into one identity; a
``:SHARES_IP`` or ``:ASSOCIATED_WITH`` edge records a co-occurrence, not sameness.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.observability.logging import get_logger
from app.orchestration.state import InvestigationState
from app.persistence.neo4j.graph_repository import GraphRepository

logger = get_logger("graph_builder")

_LABEL_BY_INDICATOR = {
    "username": "Username",
    "email": "Email",
    "domain": "Domain",
    "ip": "IpAddress",
    "wallet": "Wallet",
    "tx_hash": "Transaction",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def build_graph(state: InvestigationState, repo: GraphRepository) -> dict:
    """Write entities and provenance-carrying edges for the investigation.

    Returns a small summary (node/edge counts) for the workflow state.
    """
    case_id = state.case_id
    confidence_band = state.confidence.band if state.confidence else "unassessed"

    node_count = 0
    edge_count = 0

    # 1. Upsert indicator entities.
    typed_values: dict[str, tuple[str, str]] = {}  # value -> (label, indicator_type)
    for ind in state.indicators:
        label = _LABEL_BY_INDICATOR.get(ind.indicator_type)
        if not label:
            continue
        await repo.upsert_entity(
            case_id=case_id, label=label, value=ind.value, props={"indicator_type": ind.indicator_type}
        )
        typed_values[ind.value] = (label, ind.indicator_type)
        node_count += 1

    # 2. Upsert file entities (as File nodes keyed by sha256).
    for f in state.files:
        if not f.sha256:
            continue
        await repo.upsert_entity(
            case_id=case_id, label="File", value=f.sha256, props={"filename": f.filename}
        )
        node_count += 1

    # 3. Derive relationships from findings.
    for finding in state.findings:
        provenance = {
            "finding_summary": finding.get("summary", "")[:200],
            "source": finding.get("agent_name", "unknown"),
            "retrieved_at": finding.get("timestamp") or _now(),
            "confidence_band": confidence_band,
            "epistemic_status": finding.get("epistemic_status", "inference"),
        }
        claim = finding.get("claim_type")

        # Crypto: wallet -> counterparties (ASSOCIATED_WITH, not ownership).
        if claim == "possible_wallet_relationship":
            data = finding.get("data", {})
            wallet = data.get("wallet")
            for cp in data.get("counterparties", []):
                # Ensure counterparty node exists (as Wallet).
                await repo.upsert_entity(case_id=case_id, label="Wallet", value=cp, props={})
                node_count += 1
                if wallet in typed_values:
                    await repo.upsert_relationship(
                        case_id=case_id,
                        from_label="Wallet",
                        from_value=wallet,
                        to_label="Wallet",
                        to_value=cp,
                        rel_type="ASSOCIATED_WITH",
                        provenance=provenance,
                    )
                    edge_count += 1

    # 4. Shared-IP edges: if one IP and other indicators exist, record SHARES_IP
    #    as a co-occurrence (provenance notes it is not identity).
    ips = [v for v, (label, _t) in typed_values.items() if label == "IpAddress"]
    non_ips = [(v, label) for v, (label, _t) in typed_values.items() if label != "IpAddress"]
    if len(ips) == 1:
        ip_value = ips[0]
        for value, label in non_ips:
            await repo.upsert_relationship(
                case_id=case_id,
                from_label=label,
                from_value=value,
                to_label="IpAddress",
                to_value=ip_value,
                rel_type="SHARES_IP",
                provenance={
                    "source": "graph_builder",
                    "retrieved_at": _now(),
                    "confidence_band": confidence_band,
                    "note": "co-occurrence, not identity equivalence",
                },
            )
            edge_count += 1

    summary = {"nodes": node_count, "edges": edge_count, "built_at": _now()}
    logger.info("graph_built", case_id=case_id, **summary)
    return summary

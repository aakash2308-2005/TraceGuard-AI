"""Neo4j graph repository: provenance-aware entity and relationship writes.

Every node is scoped by ``case_id`` and every relationship carries provenance
properties (finding_id, source, retrieved_at, confidence_band, created_at). The
repository NEVER asserts identity equivalence automatically: a ``:SAME_AS`` edge
is only ever created as an explicit human-reviewed proposal (not done here).

All queries are parameterized (no Cypher string interpolation of values).
"""

from __future__ import annotations

from datetime import datetime, timezone

from neo4j import AsyncDriver

from app.observability.logging import get_logger

logger = get_logger("graph_repo")

# Map indicator types to node labels.
_LABEL_BY_INDICATOR = {
    "username": "Username",
    "email": "Email",
    "domain": "Domain",
    "ip": "IpAddress",
    "wallet": "Wallet",
    "tx_hash": "Transaction",
}

_ALLOWED_LABELS = set(_LABEL_BY_INDICATOR.values()) | {"File", "Evidence", "Finding", "Case"}
_ALLOWED_RELS = {
    "REGISTERED_BY",
    "RESOLVES_TO",
    "COMMUNICATED_WITH",
    "OWNS_CLAIMED",
    "SENT_TX",
    "RECEIVED_TX",
    "APPEARS_IN",
    "DERIVED_FROM",
    "SHARES_IP",
    "ASSOCIATED_WITH",
    "BELONGS_TO_CASE",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GraphRepository:
    def __init__(self, driver: AsyncDriver) -> None:
        self._driver = driver

    async def apply_constraints(self) -> None:
        """Create uniqueness constraints (idempotent)."""
        statements = [
            "CREATE CONSTRAINT username_key IF NOT EXISTS FOR (n:Username) "
            "REQUIRE (n.case_id, n.value) IS UNIQUE",
            "CREATE CONSTRAINT email_key IF NOT EXISTS FOR (n:Email) "
            "REQUIRE (n.case_id, n.value) IS UNIQUE",
            "CREATE CONSTRAINT domain_key IF NOT EXISTS FOR (n:Domain) "
            "REQUIRE (n.case_id, n.value) IS UNIQUE",
            "CREATE CONSTRAINT ip_key IF NOT EXISTS FOR (n:IpAddress) "
            "REQUIRE (n.case_id, n.value) IS UNIQUE",
            "CREATE CONSTRAINT wallet_key IF NOT EXISTS FOR (n:Wallet) "
            "REQUIRE (n.case_id, n.value) IS UNIQUE",
            "CREATE CONSTRAINT tx_key IF NOT EXISTS FOR (n:Transaction) "
            "REQUIRE (n.case_id, n.value) IS UNIQUE",
        ]
        async with self._driver.session() as session:
            for stmt in statements:
                await session.run(stmt)

    def _label_for(self, indicator_type: str) -> str:
        label = _LABEL_BY_INDICATOR.get(indicator_type)
        if label is None or label not in _ALLOWED_LABELS:
            raise ValueError(f"Unsupported indicator type for graph: {indicator_type}")
        return label

    async def upsert_entity(
        self, *, case_id: str, label: str, value: str, props: dict | None = None
    ) -> None:
        """Create or update an entity node (case-scoped)."""
        if label not in _ALLOWED_LABELS:
            raise ValueError(f"Disallowed node label: {label}")
        props = props or {}
        # Label is validated against an allowlist, so interpolation is safe here.
        query = (
            f"MERGE (n:{label} {{case_id: $case_id, value: $value}}) "
            "SET n += $props, n.updated_at = $now"
        )
        async with self._driver.session() as session:
            await session.run(
                query, case_id=case_id, value=value, props=props, now=_now()
            )

    async def upsert_relationship(
        self,
        *,
        case_id: str,
        from_label: str,
        from_value: str,
        to_label: str,
        to_value: str,
        rel_type: str,
        provenance: dict,
    ) -> None:
        """Create a provenance-carrying relationship between two entities."""
        if rel_type not in _ALLOWED_RELS:
            raise ValueError(f"Disallowed relationship type: {rel_type}")
        if from_label not in _ALLOWED_LABELS or to_label not in _ALLOWED_LABELS:
            raise ValueError("Disallowed node label in relationship")

        provenance = {**provenance, "created_at": provenance.get("created_at", _now())}
        query = (
            f"MATCH (a:{from_label} {{case_id: $case_id, value: $from_value}}) "
            f"MATCH (b:{to_label} {{case_id: $case_id, value: $to_value}}) "
            f"MERGE (a)-[r:{rel_type}]->(b) "
            "SET r += $provenance"
        )
        async with self._driver.session() as session:
            await session.run(
                query,
                case_id=case_id,
                from_value=from_value,
                to_value=to_value,
                provenance=provenance,
            )

    async def get_case_graph(self, case_id: str, limit: int = 2000) -> dict:
        """Return nodes and edges for a case for visualization."""
        node_query = (
            "MATCH (n {case_id: $case_id}) "
            "RETURN labels(n) AS labels, n.value AS value, properties(n) AS props "
            "LIMIT $limit"
        )
        edge_query = (
            "MATCH (a {case_id: $case_id})-[r]->(b {case_id: $case_id}) "
            "RETURN a.value AS source, b.value AS target, type(r) AS rel, "
            "properties(r) AS props LIMIT $limit"
        )
        nodes: list[dict] = []
        edges: list[dict] = []
        async with self._driver.session() as session:
            res = await session.run(node_query, case_id=case_id, limit=limit)
            async for record in res:
                labels = record["labels"]
                nodes.append(
                    {
                        "id": record["value"],
                        "label": labels[0] if labels else "Node",
                        "value": record["value"],
                        "props": dict(record["props"] or {}),
                    }
                )
            res = await session.run(edge_query, case_id=case_id, limit=limit)
            async for record in res:
                edges.append(
                    {
                        "source": record["source"],
                        "target": record["target"],
                        "rel": record["rel"],
                        "provenance": dict(record["props"] or {}),
                    }
                )
        return {"nodes": nodes, "edges": edges}

    async def clear_case(self, case_id: str) -> None:
        """Delete all nodes/edges for a case (used before a fresh rebuild)."""
        async with self._driver.session() as session:
            await session.run("MATCH (n {case_id: $case_id}) DETACH DELETE n", case_id=case_id)

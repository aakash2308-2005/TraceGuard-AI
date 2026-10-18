"""Agent registry: the single place the orchestrator resolves agents."""

from app.agents.base import Agent
from app.agents.content_agent import ContentAnalysisAgent
from app.agents.crypto_agent import CryptoAgent
from app.agents.defense_agent import DefenseAgent
from app.agents.metadata_agent import MetadataAgent
from app.agents.osint_agent import OsintAgent

# Agents that run in the parallel "agents_running" phase. The Content Analysis
# Agent runs separately (and first) in that phase so identifiers it discovers in
# uploaded files can be correlated by these agents within the same run.
PARALLEL_AGENTS: list[str] = ["osint", "metadata", "crypto"]


def build_parallel_agents() -> list[Agent]:
    """Return instances of the data-gathering agents."""
    return [OsintAgent(), MetadataAgent(), CryptoAgent()]


def build_content_agent() -> ContentAnalysisAgent:
    """Agent that scans uploaded file content for candidate identifiers."""
    return ContentAnalysisAgent()


def build_defense_agent() -> DefenseAgent:
    return DefenseAgent()

"""Content Analysis Agent: scans uploaded file *content* for identifiers.

Reads each stored file from object storage, extracts its text (plain text, PDF,
or OOXML Office), and pulls out candidate identifiers (emails, usernames,
domains, IPs, wallets, tx hashes). Each extracted string is recorded as a
verifiable *fact about the file content* — the string does appear in the
evidence — but is explicitly NOT an identity or ownership claim.

The orchestrator promotes discovered identifiers to case indicators before the
parallel agents run, so the OSINT and Crypto agents correlate them in the same
investigation. Extraction itself is fully deterministic (regex + normalization);
no content is sent to an LLM or external service.
"""

from app.agents.base import Agent
from app.config import get_settings
from app.observability.logging import get_logger
from app.orchestration.state import AgentResult, InvestigationState
from app.persistence.objstore.storage import get_object_store
from app.tools.content_extractor import extract_text
from app.tools.ioc_extractor import extract_iocs

logger = get_logger("content_agent")


class ContentAnalysisAgent(Agent):
    name = "content"

    async def run(self, state: InvestigationState) -> AgentResult:
        findings: list[dict] = []
        limitations: list[str] = []

        if not state.files:
            limitations.append("no_files_to_process")
            return AgentResult(agent_name=self.name, status="completed", limitations=limitations)

        settings = get_settings()
        store = get_object_store()
        bucket = settings.s3_bucket_evidence

        for f in state.files:
            if not f.sha256:
                limitations.append(f"missing_hash:{f.filename}")
                continue
            key = f"{state.case_id}/{f.sha256}/{f.filename}"
            try:
                data = store.get_object(bucket, key)
            except Exception as exc:  # noqa: BLE001 - degrade gracefully
                limitations.append(f"fetch_failed:{f.filename}")
                logger.warning("content_fetch_failed", filename=f.filename, error=str(exc))
                continue

            extraction = extract_text(
                data, filename=f.filename, mime_type=f.mime_type
            )
            limitations.extend(
                f"{f.filename}:{lim}" for lim in extraction.limitations
            )
            if not extraction.text.strip():
                limitations.append(f"no_text_extracted:{f.filename}")
                continue

            iocs = extract_iocs(extraction.text)
            if not iocs:
                limitations.append(f"no_identifiers_found:{f.filename}")
                continue

            preview = ", ".join(f"{i.indicator_type}: {i.value}" for i in iocs[:10])
            if len(iocs) > 10:
                preview += f", +{len(iocs) - 10} more"
            findings.append(
                {
                    "summary": (
                        f"Found {len(iocs)} candidate identifier(s) in {f.filename}: "
                        f"{preview} (present in file content; ownership not established)."
                    ),
                    "epistemic_status": "fact",
                    "claim_type": "extracted_identifier",
                    "filename": f.filename,
                    "sha256": f.sha256,
                    "indicators": [
                        {
                            "indicator_type": ioc.indicator_type,
                            "value": ioc.value,
                            "count": ioc.count,
                        }
                        for ioc in iocs
                    ],
                    "text_chars": len(extraction.text),
                    "truncated": extraction.truncated,
                }
            )

        return AgentResult(
            agent_name=self.name,
            status="completed",
            findings=findings,
            limitations=limitations,
        )

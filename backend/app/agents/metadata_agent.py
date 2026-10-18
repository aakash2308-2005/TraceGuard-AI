"""Forensic Metadata Agent: extracts metadata from uploaded files.

Runs the sandboxed ExifTool tool against each stored file and records timestamps
and GPS as *metadata claims* (never independently verified facts). File bytes
are read from object storage using the deterministic storage-key convention set
at upload: ``{case_id}/{sha256}/{filename}``.
"""

from app.agents.base import Agent
from app.config import get_settings
from app.observability.logging import get_logger
from app.orchestration.state import AgentResult, InvestigationState
from app.persistence.objstore.storage import get_object_store
from app.tools.exiftool_runner import extract_metadata

logger = get_logger("metadata_agent")


class MetadataAgent(Agent):
    name = "metadata"

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
                logger.warning("metadata_fetch_failed", filename=f.filename, error=str(exc))
                continue

            suffix = "." + f.filename.rsplit(".", 1)[1] if "." in f.filename else ""
            exif = extract_metadata(data, suffix=suffix)
            limitations.extend(exif.limitations)

            if exif.timestamps or exif.gps or exif.metadata:
                findings.append(
                    {
                        "summary": f"Metadata extracted from {f.filename} (unverified claims).",
                        "epistemic_status": "unverified_claim",
                        "claim_type": "file_metadata",
                        "filename": f.filename,
                        "sha256": f.sha256,
                        "metadata": exif.metadata,
                        "gps": exif.gps,
                        "timestamp": next(iter(exif.timestamps.values()), None),
                        "timestamps": exif.timestamps,
                    }
                )

        return AgentResult(
            agent_name=self.name,
            status="completed",
            findings=findings,
            limitations=limitations,
        )

"""Tests for file-content text extraction, IOC extraction, and the Content Agent."""

import io
import uuid
import zipfile

import pytest

from app.agents import content_agent as content_agent_module
from app.agents.content_agent import ContentAnalysisAgent
from app.orchestration.engine import Orchestrator
from app.orchestration.state import (
    AgentResult,
    FileRef,
    IndicatorRef,
    InvestigationState,
)
from app.tools.content_extractor import (
    DOCX_MIME,
    PDF_MIME,
    XLSX_MIME,
    extract_text,
)
from app.tools.file_validation import validate_file
from app.tools.ioc_extractor import extract_iocs


# --- Helpers to build minimal OOXML containers ---
def _docx_bytes(paragraphs: list[str]) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    xml = (
        '<?xml version="1.0"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    ).encode()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", xml)
    return buf.getvalue()


def _xlsx_bytes(strings: list[str]) -> bytes:
    items = "".join(f"<si><t>{s}</t></si>" for s in strings)
    xml = (
        '<?xml version="1.0"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"{items}</sst>"
    ).encode()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("xl/sharedStrings.xml", xml)
    return buf.getvalue()


def _state(files=None, indicators=None) -> InvestigationState:
    return InvestigationState(
        investigation_id=str(uuid.uuid4()),
        case_id=str(uuid.uuid4()),
        started_by=str(uuid.uuid4()),
        files=files or [],
        indicators=indicators or [],
    )


# --- IOC extraction ---
def test_extract_iocs_finds_common_identifiers():
    text = (
        "Contact alice@example.com or visit https://portal.evil-corp.net/login. "
        "Server 203.0.113.7 was used. "
        "Pay to 0x" + "a" * 40 + " (tx 0x" + "b" * 64 + "). "
        "username: shadowfox and ping @shadowfox."
    )
    found = {(i.indicator_type, i.value): i.count for i in extract_iocs(text)}
    assert ("email", "alice@example.com") in found
    assert ("domain", "portal.evil-corp.net") in found
    assert ("ip", "203.0.113.7") in found
    assert ("wallet", "0x" + "a" * 40) in found
    assert ("tx_hash", "0x" + "b" * 64) in found
    assert found[("username", "shadowfox")] == 2  # labelled field + @mention


def test_extract_iocs_does_not_double_count_email_domain():
    found = {i.indicator_type for i in extract_iocs("mail bob@example.com now")}
    assert "email" in found
    assert "domain" not in found  # example.com is part of the email, not a separate domain


def test_extract_iocs_drops_file_extension_domains():
    found = extract_iocs("see report.txt and notes.pdf and image.png")
    assert [i for i in found if i.indicator_type == "domain"] == []


def test_extract_iocs_rejects_invalid_ip():
    found = extract_iocs("version 999.1.1.1 shipped")
    assert [i for i in found if i.indicator_type == "ip"] == []


# --- Text extraction ---
def test_extract_text_plain():
    result = extract_text(b"hello username: bob", filename="a.txt", mime_type="text/plain")
    assert "hello username: bob" in result.text
    assert result.kind == "text/plain"


def test_extract_text_docx():
    result = extract_text(_docx_bytes(["user: alice", "ip 10.0.0.5"]), filename="a.docx")
    assert "alice" in result.text
    assert "10.0.0.5" in result.text


def test_extract_text_xlsx():
    result = extract_text(
        _xlsx_bytes(["harry@example.org"]), filename="a.xlsx", mime_type=XLSX_MIME
    )
    assert "harry@example.org" in result.text


def test_extract_text_unsupported_type():
    result = extract_text(b"\x00\x01", filename="a.bin", mime_type="application/octet-stream")
    assert result.text == ""
    assert "unsupported_content_type" in result.limitations


def test_extract_text_corrupt_pdf_degrades():
    result = extract_text(b"not really a pdf", filename="a.pdf", mime_type=PDF_MIME)
    assert result.text == ""
    assert any(lim.startswith("pdf_") for lim in result.limitations)


# --- Upload validation for the new formats ---
def test_docx_magic_passes_validation():
    data = _docx_bytes(["hello"])
    result = validate_file(data=data, declared_mime=DOCX_MIME, filename="a.docx")
    assert result.mime_type == DOCX_MIME


def test_csv_text_passes_validation():
    result = validate_file(
        data=b"name,email\nalice,alice@example.com\n", declared_mime="text/csv", filename="a.csv"
    )
    assert result.mime_type == "text/csv"


def test_json_passes_validation():
    result = validate_file(
        data=b'{"user": "bob"}', declared_mime="application/json", filename="a.json"
    )
    assert result.mime_type == "application/json"


# --- Content agent ---
class _FakeStore:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self._objects = objects

    def get_object(self, bucket: str, key: str) -> bytes:  # noqa: ARG002
        return self._objects[key]


@pytest.mark.asyncio
async def test_content_agent_extracts_identifiers_from_file(monkeypatch):
    sha = "d" * 64
    data = b"username: shadowfox email shadowfox@example.com ip 198.51.100.9"
    store = _FakeStore({f"case/{sha}/notes.txt": data})
    monkeypatch.setattr(content_agent_module, "get_object_store", lambda: store)

    state = _state(
        files=[
            FileRef(
                evidence_id="e1",
                filename="notes.txt",
                sha256=sha,
                mime_type="text/plain",
            )
        ]
    )
    state.case_id = "case"

    result = await ContentAnalysisAgent().run(state)
    assert result.status == "completed"
    assert len(result.findings) == 1
    values = {(i["indicator_type"], i["value"]) for i in result.findings[0]["indicators"]}
    assert ("username", "shadowfox") in values
    assert ("email", "shadowfox@example.com") in values
    assert ("ip", "198.51.100.9") in values
    # Presence-only finding: fact about content, not an ownership claim.
    assert result.findings[0]["epistemic_status"] == "fact"


@pytest.mark.asyncio
async def test_content_agent_handles_no_files():
    result = await ContentAnalysisAgent().run(_state())
    assert "no_files_to_process" in result.limitations


# --- Indicator promotion (orchestrator) ---
class _FakeResult:
    def __init__(self, rows=None) -> None:
        self._rows = rows or []

    def all(self):
        return self._rows

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalars(self):
        return self


class _FakeSession:
    """Minimal async session stand-in: records objects, assigns ids on flush."""

    def __init__(self) -> None:
        self.added: list = []

    async def execute(self, _stmt):  # noqa: ARG002
        return _FakeResult()

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()


@pytest.mark.asyncio
async def test_register_extracted_indicators_promotes_and_dedupes():
    orch = Orchestrator(uuid.uuid4())
    state = _state(
        indicators=[IndicatorRef(evidence_id="e1", indicator_type="email", value="known@x.com")]
    )
    session = _FakeSession()
    result = AgentResult(
        agent_name="content",
        status="completed",
        findings=[
            {
                "filename": "notes.txt",
                "indicators": [
                    {"indicator_type": "email", "value": "known@x.com"},  # already present
                    {"indicator_type": "username", "value": "shadowfox"},
                    {"indicator_type": "ip", "value": "198.51.100.9"},
                    {"indicator_type": "username", "value": "BAD VALUE"},  # invalid -> skipped
                ],
            }
        ],
    )

    created = await orch._register_extracted_indicators(state, session, result)
    assert created == 2
    promoted = {(i.indicator_type, i.value) for i in state.indicators}
    assert ("username", "shadowfox") in promoted
    assert ("ip", "198.51.100.9") in promoted
    # Indicator evidence rows were added with provenance.
    indicator_rows = [e for e in session.added if getattr(e, "type", None) == "indicator"]
    assert indicator_rows
    assert all(e.source.startswith("content_extraction:") for e in indicator_rows)


@pytest.mark.asyncio
async def test_register_extracted_indicators_respects_cap(monkeypatch):
    orch = Orchestrator(uuid.uuid4())
    monkeypatch.setattr(orch._settings, "content_max_indicators_per_run", 1)
    state = _state()
    result = AgentResult(
        agent_name="content",
        status="completed",
        findings=[
            {
                "filename": "bulk.csv",
                "indicators": [
                    {"indicator_type": "email", "value": "a@x.com"},
                    {"indicator_type": "email", "value": "b@x.com"},
                    {"indicator_type": "email", "value": "c@x.com"},
                ],
            }
        ],
    )

    created = await orch._register_extracted_indicators(state, _FakeSession(), result)
    assert created == 1

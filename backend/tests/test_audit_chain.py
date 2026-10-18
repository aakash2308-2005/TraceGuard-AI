"""Unit tests for the audit hash-chain primitive (no DB required)."""

from app.services.audit_service import _GENESIS, compute_entry_hash


def test_hash_is_deterministic():
    payload = {"action": "case.created", "actor_id": "u1", "detail": {"title": "x"}}
    h1 = compute_entry_hash(_GENESIS, payload)
    h2 = compute_entry_hash(_GENESIS, payload)
    assert h1 == h2
    assert len(h1) == 64


def test_chain_links_change_with_prev():
    payload = {"action": "x", "detail": {}}
    first = compute_entry_hash(_GENESIS, payload)
    second = compute_entry_hash(first, payload)
    # Same payload but different prev_hash -> different entry hash (chaining).
    assert first != second


def test_payload_change_breaks_hash():
    base = compute_entry_hash(_GENESIS, {"action": "a", "detail": {}})
    altered = compute_entry_hash(_GENESIS, {"action": "a", "detail": {"x": 1}})
    assert base != altered

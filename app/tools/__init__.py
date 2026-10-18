"""Deterministic tools: pure, testable adapters to external capabilities.

Tools perform all verifiable operations (hashing, metadata extraction, external
lookups). Agents call tools; tools never call agents. This keeps verifiable work
reproducible and unit-testable (NFR-005).
"""

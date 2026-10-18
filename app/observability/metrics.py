"""Prometheus metrics for requests, agents, external calls, and jobs (OBS-002)."""

from prometheus_client import Counter, Gauge, Histogram

REQUEST_LATENCY = Histogram(
    "traceguard_request_latency_seconds",
    "HTTP request latency in seconds",
    labelnames=("method", "path", "status"),
)

AGENT_DURATION = Histogram(
    "traceguard_agent_duration_seconds",
    "Agent execution duration in seconds",
    labelnames=("agent",),
)

EXTERNAL_CALL_LATENCY = Histogram(
    "traceguard_external_call_latency_seconds",
    "External API call latency in seconds",
    labelnames=("source",),
)

EXTERNAL_CALL_FAILURES = Counter(
    "traceguard_external_call_failures_total",
    "Total external API call failures",
    labelnames=("source",),
)

INVESTIGATION_STATUS = Gauge(
    "traceguard_investigations_in_state",
    "Number of investigations currently in a given state",
    labelnames=("state",),
)

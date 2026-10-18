import { describe, expect, it } from "vitest";
import type { EpistemicStatus, Finding } from "../api/types";
import { epistemicRank, findingMeta, orderFindings } from "./epistemic";

const finding = (
  status: EpistemicStatus,
  agent: string,
  timestamp?: string,
  claim?: string,
): Finding => ({
  agent_name: agent,
  epistemic_status: status,
  claim_type: claim ?? null,
  payload: timestamp ? { timestamp } : {},
});

describe("orderFindings", () => {
  it("orders by evidence strength first, then oldest event first", () => {
    const rows = [
      finding("hypothesis", "Content", "2026-01-01T00:00:00Z"),
      finding("fact", "Crypto", "2026-03-01T00:00:00Z"),
      finding("fact", "OSINT", "2026-02-01T00:00:00Z"),
      finding("inference", "Metadata", "2026-01-05T00:00:00Z"),
      finding("unverified_claim", "OSINT", "2026-01-10T00:00:00Z"),
    ];

    const out = orderFindings(rows);

    expect(out.map((f) => f.epistemic_status)).toEqual([
      "fact",
      "fact",
      "unverified_claim",
      "inference",
      "hypothesis",
    ]);
    // Chronological within the facts group.
    expect(out[0].agent_name).toBe("OSINT");
    expect(out[1].agent_name).toBe("Crypto");
  });

  it("breaks timestamp ties by agent name, and never mutates the input", () => {
    const rows = [
      finding("fact", "Zeta", "2026-01-01T00:00:00Z"),
      finding("fact", "Alpha", "2026-01-01T00:00:00Z"),
    ];
    const snapshot = [...rows];

    const out = orderFindings(rows);

    expect(out.map((f) => f.agent_name)).toEqual(["Alpha", "Zeta"]);
    expect(rows).toEqual(snapshot);
  });

  it("sorts unknown statuses and missing timestamps last", () => {
    const rows = [
      finding("fact", "Late", "2026-05-01T00:00:00Z"),
      { ...finding("fact", "NoTime"), epistemic_status: "vibes" as EpistemicStatus },
      finding("fact", "NoTimestamp"),
    ];

    const out = orderFindings(rows);

    // Missing timestamps sort after real ones; unknown statuses sort last.
    expect(out.map((f) => f.agent_name)).toEqual(["Late", "NoTimestamp", "NoTime"]);
    expect(epistemicRank("vibes")).toBeGreaterThan(epistemicRank("hypothesis"));
  });
});

describe("findingMeta", () => {
  it("joins claim, agent and timestamp — omitting what is absent", () => {
    expect(
      findingMeta(finding("fact", "osint_agent", "2026-01-01T00:00:00Z", "wallet_link")),
    ).toBe("Wallet Link · Agent: Osint Agent · 2026-01-01T00:00:00Z");
    expect(findingMeta(finding("fact", "crypto_agent"))).toBe("Agent: Crypto Agent");
  });
});

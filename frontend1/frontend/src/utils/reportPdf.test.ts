import { describe, expect, it } from "vitest";
import type { Report } from "../api/types";
import { buildReportPdf } from "./reportPdf";

const report: Report = {
  id: "11111111-2222-3333-4444-555555555555",
  run_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  status: "approved",
  content: {
    case_id: "99999999-8888-7777-6666-555555555555",
    narrative:
      "The pipeline correlated wallet activity with OSINT reporting. — em-dash, curly “quotes”, ellipsis… survive.",
    hypothesis: "Funds moved through a chain of peel wallets before exiting to a mixer.",
    facts: [{ summary: "Wallet 0xA received 2.4 ETH at 2026-01-03." }],
    unverified_claims: [
      { summary: "An underground forum post claims the wallet belongs to a known actor." },
      { summary: "A second claim: the exchange account was opened with stolen KYC.", flagged_uncited: true },
    ],
    inferences: [{ summary: "Timing overlaps with the phishing campaign window." }],
    hypotheses: [{ summary: "The actor reuses infrastructure across campaigns." }],
    contradictions: [
      {
        kind: "verified_contradiction",
        description: "Reported withdrawal address differs from the observed one.",
        basis: "On-chain record.",
      },
      { kind: "plausible_alternative", description: "Funds could belong to a service hot wallet." },
    ],
    open_questions: ["Who controls the exit exchange account?"],
    limitations: ["No visibility into off-chain internal transfers."],
  },
  content_hash: "sha256:0000000000000000000000000000000000000000000000000000000000000000",
  approved_by: "admin",
  approved_at: "2026-10-17T12:30:00Z",
  created_at: "2026-10-17T12:00:00Z",
};

describe("buildReportPdf", () => {
  it("renders a valid PDF with the standard header", () => {
    const doc = buildReportPdf(report, {
      name: "Ada Lovelace",
      email: "ada@traceguard.local",
      username: "ada",
    });
    const bytes = doc.output("arraybuffer");
    const head = new TextDecoder("latin1").decode(new Uint8Array(bytes, 0, 5));
    expect(head).toBe("%PDF-");
    expect(bytes.byteLength).toBeGreaterThan(2_000);
    expect(doc.getNumberOfPages()).toBeGreaterThanOrEqual(1);
  });

  it("paginates many findings instead of overflowing", () => {
    const long: Report = {
      ...report,
      content: {
        ...report.content,
        facts: Array.from({ length: 40 }, (_, i) => ({
          summary: `Finding ${i + 1}: wallet activity correlated with the campaign window and traced to the exit exchange.`,
          agent: "payment-service-osint",
          claim_type: "observation",
        })),
      },
    };
    expect(buildReportPdf(long).getNumberOfPages()).toBeGreaterThan(1);
  });
});

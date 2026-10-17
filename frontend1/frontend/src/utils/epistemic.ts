
import type { EpistemicStatus, Finding } from "../api/types";
import { titleCase } from "./format";

export interface EpistemicGroup {
  /** Report content section key. */
  key: string;
  status: EpistemicStatus;
  label: string;
  blurb: string;
}

export const EPISTEMIC_ORDER: EpistemicGroup[] = [
  { key: "facts", status: "fact", label: "Facts", blurb: "Independently observed and sourced." },
  {
    key: "unverified_claims",
    status: "unverified_claim",
    label: "Unverified claims",
    blurb: "Reported but not corroborated.",
  },
  { key: "inferences", status: "inference", label: "Inferences", blurb: "Reasoned connections — not proof." },
  {
    key: "hypotheses",
    status: "hypothesis",
    label: "Hypotheses",
    blurb: "Testable explanations for observed facts — not confirmed conclusions.",
  },
];

/** Reading rank of a status; anything unrecognised sorts last. */
export function epistemicRank(status: string): number {
  const i = EPISTEMIC_ORDER.findIndex((g) => g.status === status);
  return i === -1 ? EPISTEMIC_ORDER.length : i;
}

/** Event time of a finding for chronological ordering (missing → last). */
function eventTime(f: Finding): number {
  const ts = f.payload.timestamp;
  if (typeof ts === "number" && Number.isFinite(ts)) return ts;
  const parsed = Date.parse(String(ts ?? ""));
  return Number.isFinite(parsed) ? parsed : Number.MAX_SAFE_INTEGER;
}


export function orderFindings(rows: Finding[]): Finding[] {
  return [...rows].sort((a, b) => {
    const rank = epistemicRank(a.epistemic_status) - epistemicRank(b.epistemic_status);
    if (rank !== 0) return rank;
    const dt = eventTime(a) - eventTime(b);
    if (dt !== 0) return dt;
    return a.agent_name.localeCompare(b.agent_name);
  });
}

/** The one-line metadata shown under a finding's summary (UI and PDF). */
export function findingMeta(f: Finding): string {
  return [
    f.claim_type ? titleCase(f.claim_type) : null,
    `Agent: ${titleCase(f.agent_name)}`,
    f.payload.timestamp ? String(f.payload.timestamp) : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

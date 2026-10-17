import type { EpistemicStatus } from "../api/types";
import { StatusPill } from "./common";

// Epistemic status is conveyed by an explicit LABEL + ICON, never color alone
// (A11Y-002, FR-023). Color is a secondary reinforcement only.
const CONFIG: Record<EpistemicStatus, { label: string; icon: string; mod: string }> = {
  fact: { label: "FACT", icon: "✓", mod: "tg-chip-fact" },
  unverified_claim: { label: "UNVERIFIED CLAIM", icon: "?", mod: "tg-chip-claim" },
  inference: { label: "INFERENCE", icon: "~", mod: "tg-chip-inference" },
  hypothesis: { label: "HYPOTHESIS", icon: "∴", mod: "tg-chip-hypothesis" },
};

export function StatusChip({ status }: { status: EpistemicStatus }) {
  const cfg = CONFIG[status] ?? CONFIG.inference;
  return (
    <span
      className={`tg-chip ${cfg.mod}`}
      role="img"
      aria-label={`Epistemic status: ${cfg.label}`}
    >
      <span aria-hidden="true">{cfg.icon}</span>
      {cfg.label}
    </span>
  );
}

// Generic status pill for investigation/evidence states.
export function StatePill({ value }: { value: string }) {
  return <StatusPill value={value} />;
}

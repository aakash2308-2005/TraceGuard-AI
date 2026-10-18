// Presentation helpers for mapping backend status strings to UI tones.

// Severity language lives in the tone ladder: "high" (orange) needs prompt
// attention, "warning" (amber) is a medium-level state. Case status and
// severity stay distinct — an active case can still be high or medium.
export type Tone = "neutral" | "info" | "success" | "warning" | "high" | "error";

// Maps free-form backend status strings to a presentation tone. The text label
// remains the source of truth — the tone is only reinforcement.
export function statusTone(value: string | null | undefined): Tone {
  const v = (value ?? "").toLowerCase();
  if (["verified", "approved", "active", "completed", "complete", "success", "ok", "yes"].includes(v)) {
    return "success";
  }
  if (
    [
      "running",
      "pending",
      "in_progress",
      "agents_running",
      "validating",
      "hashing",
      "planning",
      "normalizing",
      "graphing",
      "timeline",
      "defense",
      "confidence",
      "report_draft",
      "awaiting_review",
      "draft",
      "processing",
    ].includes(v)
  ) {
    return "info";
  }
  if (
    ["failed", "error", "mismatch", "rejected", "cancelled", "canceled", "invalid", "no"].includes(v)
  ) {
    return "error";
  }
  // High severity (orange): flagged / needs review / paused — prompt attention.
  if (["flagged", "needs_review", "paused"].includes(v)) {
    return "high";
  }
  // Medium severity (amber): suspicious states that need a look.
  if (["warning", "unverified", "partial"].includes(v)) {
    return "warning";
  }
  return "neutral";
}

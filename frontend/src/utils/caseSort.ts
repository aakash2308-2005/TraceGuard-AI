// Sorting for the Cases list. Kept out of the page component so lint's
// fast-refresh rule (component files may only export components) stays clean
// and the ordering rules can be unit-tested directly.

import type { CaseItem } from "../api/types";

export type CaseSortKey = "identifier" | "title" | "status" | "role" | "created";

export interface CaseSort {
  key: CaseSortKey;
  dir: "asc" | "desc";
}

/** Newest case first — the default so recent cases sit on top. */
export const DEFAULT_CASE_SORT: CaseSort = { key: "created", dir: "desc" };

/** Human label for each column + direction (drives the "Sort by" control). */
export const SORT_LABELS: Record<CaseSortKey, { asc: string; desc: string }> = {
  identifier: { asc: "Case ID A–Z", desc: "Case ID Z–A" },
  title: { asc: "Title A–Z", desc: "Title Z–A" },
  status: { asc: "Status A–Z", desc: "Status Z–A" },
  role: { asc: "Role A–Z", desc: "Role Z–A" },
  created: { asc: "Oldest first", desc: "Newest first" },
};

export const sortLabel = (sort: CaseSort): string => SORT_LABELS[sort.key][sort.dir];

/** Pure sort helper: returns a new, ordered array; never mutates the input. */
export function sortCases(items: CaseItem[], sort: CaseSort): CaseItem[] {
  const dir = sort.dir === "asc" ? 1 : -1;
  const cmp = (a: CaseItem, b: CaseItem): number => {
    switch (sort.key) {
      case "identifier":
        return a.case_identifier.localeCompare(b.case_identifier, undefined, {
          sensitivity: "base",
        });
      case "title":
        return a.title.localeCompare(b.title, undefined, { sensitivity: "base" });
      case "status":
        return a.status.localeCompare(b.status);
      case "role":
        return (a.my_case_role ?? "").localeCompare(b.my_case_role ?? "", undefined, {
          sensitivity: "base",
        });
      case "created":
        return Date.parse(a.created_at) - Date.parse(b.created_at);
      default:
        return 0;
    }
  };
  // Copy first so the query cache is never mutated; Array#sort is stable, so
  // cases sharing a timestamp keep their relative order.
  return [...items].sort((a, b) => cmp(a, b) * dir);
}

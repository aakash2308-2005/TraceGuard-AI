import { describe, expect, it } from "vitest";
import type { CaseItem } from "../api/types";
import { DEFAULT_CASE_SORT, sortCases, sortLabel } from "./caseSort";

const makeCase = (over: Partial<CaseItem> & { id: string }): CaseItem => ({
  case_identifier: `CASE-${over.id}`,
  title: over.id,
  description: null,
  status: "active",
  created_by: "user-1",
  created_at: "2026-01-01T00:00:00Z",
  archived_at: null,
  my_case_role: null,
  ...over,
});

const ids = (items: CaseItem[]) => items.map((c) => c.id);

describe("sortCases", () => {
  const older = makeCase({ id: "old", created_at: "2026-01-05T10:00:00Z" });
  const newer = makeCase({ id: "new", created_at: "2026-03-20T10:00:00Z" });
  const middle = makeCase({ id: "mid", created_at: "2026-02-10T10:00:00Z" });

  it("defaults to newest first (recent cases on top)", () => {
    expect(DEFAULT_CASE_SORT).toEqual({ key: "created", dir: "desc" });
    expect(ids(sortCases([older, newer, middle], DEFAULT_CASE_SORT))).toEqual([
      "new",
      "mid",
      "old",
    ]);
  });

  it("flips to oldest first on ascending date", () => {
    expect(ids(sortCases([newer, older, middle], { key: "created", dir: "asc" }))).toEqual([
      "old",
      "mid",
      "new",
    ]);
  });

  it("sorts text columns alphabetically in both directions", () => {
    const cases = [
      makeCase({ id: "b", title: "Phishing case", case_identifier: "CASE-2" }),
      makeCase({ id: "a", title: "Malware case", case_identifier: "CASE-1" }),
    ];
    expect(ids(sortCases(cases, { key: "title", dir: "asc" }))).toEqual(["a", "b"]);
    expect(ids(sortCases(cases, { key: "title", dir: "desc" }))).toEqual(["b", "a"]);
    expect(ids(sortCases(cases, { key: "identifier", dir: "asc" }))).toEqual(["a", "b"]);
  });

  it("treats a missing case role as empty text", () => {
    const cases = [
      makeCase({ id: "lead", my_case_role: "lead" }),
      makeCase({ id: "none", my_case_role: null }),
    ];
    expect(ids(sortCases(cases, { key: "role", dir: "asc" }))).toEqual(["none", "lead"]);
    expect(ids(sortCases(cases, { key: "role", dir: "desc" }))).toEqual(["lead", "none"]);
  });

  it("returns a new array and keeps ties in their original order", () => {
    const sameTime = [makeCase({ id: "first" }), makeCase({ id: "second" })];
    const out = sortCases(sameTime, DEFAULT_CASE_SORT);
    expect(out).not.toBe(sameTime);
    expect(ids(sameTime)).toEqual(["first", "second"]);
    expect(ids(out)).toEqual(["first", "second"]);
  });

  it("labels every option the Sort by menu can pick", () => {
    expect(sortLabel(DEFAULT_CASE_SORT)).toBe("Newest first");
    expect(sortLabel({ key: "created", dir: "asc" })).toBe("Oldest first");
    expect(sortLabel({ key: "identifier", dir: "asc" })).toBe("Case ID A–Z");
    expect(sortLabel({ key: "title", dir: "desc" })).toBe("Title Z–A");
  });
});

/**
 * Export + clipboard helpers for indicator data.
 *
 * These are intentionally dependency-free: the CSV writer and STIX bundle
 * builder are small enough that pulling in a library would cost far more in
 * bundle size than it saves.
 */

export interface ExportableIndicator {
  value: string;
  type: string;
  status?: string;
  note?: string;
  first_seen?: string;
  last_seen?: string;
}

/* ------------------------------------------------------------ clipboard --- */

/** Copy text, with a textarea fallback for non-secure contexts. */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* fall through to the legacy path */
  }
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

/* ----------------------------------------------------------------- CSV ---- */

function csvCell(value: unknown): string {
  const s = value == null ? "" : String(value);
  // Escape if it contains a delimiter, quote, or newline — and double quotes.
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function toCSV(headers: string[], rows: (string | number | null | undefined)[][]): string {
  const lines = [headers.map(csvCell).join(",")];
  for (const row of rows) lines.push(row.map(csvCell).join(","));
  // BOM so Excel opens UTF-8 indicator values (emoji, non-Latin) correctly.
  return "\ufeff" + lines.join("\r\n");
}

/* ---------------------------------------------------------------- JSON ---- */

export function toJSONFile(payload: unknown, pretty = true): string {
  return JSON.stringify(payload, null, pretty ? 2 : 0);
}

/* --------------------------------------------------------------- STIX ----- */

const uuidish = (seed: string): string => {
  // Deterministic pseudo-UUID so re-exporting the same case yields a stable
  // bundle id rather than changing on every download.
  let h = 2166136261;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  const hex = (h >>> 0).toString(16).padStart(8, "0");
  const rev = [...seed].reduce((a, c) => (a * 31 + c.charCodeAt(0)) >>> 0, 7).toString(16);
  return `${hex}-0000-4000-8000-${hex.slice(0, 4)}${rev.padStart(4, "0")}`;
};

function stixPattern(ind: ExportableIndicator): { pattern: string; type: string } | null {
  const v = ind.value.trim();
  switch (ind.type.toLowerCase()) {
    case "domain":
    case "domain_name":
      return { pattern: `[domain-name:value = '${v}']`, type: "domain-name" };
    case "email":
    case "email_address":
      return { pattern: `[email-addr:value = '${v}']`, type: "email-addr" };
    case "ipaddress":
    case "ip": {
      // A colon only appears in IPv6 literals, never in IPv4.
      const isV6 = v.includes(":");
      return { pattern: `[${isV6 ? "ipv6-addr" : "ipv4-addr"}:value = '${v}']`, type: isV6 ? "ipv6-addr" : "ipv4-addr" };
    }
    case "file":
    case "hash":
    case "sha256": {
      // Only emit a hash pattern when the value actually looks like a digest
      // of a known length; otherwise fall through to the namespaced form.
      const hex = /^[a-f0-9]+$/i.test(v);
      const algo = hex && v.length === 64 ? "SHA-256" : hex && v.length === 40 ? "SHA-1" : hex && v.length === 32 ? "MD5" : null;
      if (algo) return { pattern: `[file:hashes.'${algo}' = '${v}']`, type: "file" };
      return { pattern: `[x-traceguard-file:value = '${v}']`, type: "x-traceguard-indicator" };
    }
    case "url":
      return { pattern: `[url:value = '${v}']`, type: "url" };
    default:
      // No STIX observable type for usernames/wallets in the core spec — emit
      // a namespaced extension so nothing is silently dropped from the bundle.
      return { pattern: `[x-traceguard-${ind.type.toLowerCase()}:value = '${v}']`, type: "x-traceguard-indicator" };
  }
}

export function toSTIX(caseTitle: string, indicators: ExportableIndicator[], generatedAt = new Date()): string {
  const iso = generatedAt.toISOString();
  const identityId = `identity--${uuidish(`identity:${caseTitle}`)}`;

  const objects: Array<Record<string, unknown>> = [
    {
      type: "identity",
      spec_version: "2.1",
      id: identityId,
      name: "TraceGuard AI",
      description: "Automated investigative export; human-supervised.",
      identity_class: "system",
      created: iso,
      modified: iso,
    },
  ];

  for (const ind of indicators) {
    const built = stixPattern(ind);
    if (!built) continue;
    objects.push({
      type: "indicator",
      spec_version: "2.1",
      id: `indicator--${uuidish(`${ind.type}:${ind.value}`)}`,
      created_by_ref: identityId,
      name: `${ind.type}: ${ind.value}`,
      description: ind.note ?? "",
      pattern: built.pattern,
      pattern_type: "stix",
      valid_from: ind.first_seen ?? iso,
      labels: ["observed-data"],
    });
  }

  return toJSONFile({
    type: "bundle",
    id: `bundle--${uuidish(`bundle:${caseTitle}:${indicators.length}`)}`,
    objects,
  });
}

/* ------------------------------------------------------------- download --- */

export function downloadText(filename: string, content: string, mime: string): void {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Revoke on the next tick so the download has grabbed the bytes.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function slugify(input: string): string {
  return (
    input
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 60) || "case"
  );
}

/* --------------------------------------------------------------- combos --- */

export function exportIndicators(
  format: "csv" | "json" | "stix",
  caseTitle: string,
  indicators: ExportableIndicator[],
): { filename: string; mime: string; content: string } {
  const stamp = new Date().toISOString().slice(0, 10);
  const base = `${slugify(caseTitle)}-indicators-${stamp}`;

  if (format === "csv") {
    return {
      filename: `${base}.csv`,
      mime: "text/csv",
      content: toCSV(
        ["value", "type", "status", "first_seen", "last_seen", "note"],
        indicators.map((i) => [i.value, i.type, i.status, i.first_seen, i.last_seen, i.note]),
      ),
    };
  }

  if (format === "json") {
    return {
      filename: `${base}.json`,
      mime: "application/json",
      content: toJSONFile({
        case: caseTitle,
        generated_at: new Date().toISOString(),
        source: "TraceGuard AI",
        indicator_count: indicators.length,
        indicators,
      }),
    };
  }

  return {
    filename: `${base}.stix.json`,
    mime: "application/json",
    content: toSTIX(caseTitle, indicators),
  };
}

/**
 * Client-side PDF rendering of an investigation report.
 *
 * jsPDF draws the standard-14 fonts (Helvetica / Helvetica-Bold / Courier)
 * directly, so no font files ship with the bundle; layout is measured with the
 * library's own text metrics. Everything is laid out in millimetres on A4 and
 * follows the same reading order as the app: particulars box (name, email,
 * username, hypothesis) → report metadata → findings (point-wise, strongest
 * evidence first) → defence (counter-arguments, point-wise).
 */
import { jsPDF } from "jspdf";
import type { Report } from "../api/types";
import { EPISTEMIC_ORDER } from "./epistemic";
import { formatDateTime, titleCase } from "./format";

type RGB = [number, number, number];

const PAGE_W = 210;
const PAGE_H = 297;
const MARGIN = 18;
const CONTENT_W = PAGE_W - MARGIN * 2;
const BOTTOM = PAGE_H - MARGIN - 4;

// Brand palette — mirrors the app tokens (#7566E8 accent, dark ink).
const VIOLET: RGB = [117, 102, 232];
const VIOLET_DEEP: RGB = [91, 77, 214];
const INK: RGB = [27, 21, 51];
const MUTED: RGB = [101, 112, 139];
const RULE: RGB = [226, 223, 238];
const SOFT: RGB = [243, 241, 252];
const GREEN: RGB = [23, 128, 86];
const RED: RGB = [176, 42, 55];
const AMBER: RGB = [160, 106, 12];

/**
 * Standard-14 fonts are Latin-1: normalise typographic punctuation so
 * em-dashes and curly quotes survive, drop control codes, and fall back to
 * '?' for anything the font cannot draw — bytes must stay metric-compatible
 * with the encoding.
 */
function pdfText(value: unknown): string {
  const raw = String(value ?? "")
    .replace(/[\u2018\u2019\u201A]/g, "'")
    .replace(/[\u201C\u201D\u201E]/g, '"')
    .replace(/[\u2013\u2014]/g, "-")
    .replace(/\u2026/g, "...")
    .replace(/\u00A0/g, " ");
  let out = "";
  for (const ch of raw) {
    const code = ch.codePointAt(0) ?? 0;
    if (code === 0x0a || code === 0x0d || code === 0x09) {
      out += " ";
      continue;
    }
    if (code < 0x20 || code === 0x7f) continue;
    out += code <= 0xff ? ch : "?";
  }
  return out;
}

/** Identity shown in the report's particulars box (from /auth/me). */
export interface ReportAuthor {
  name?: string | null;
  email?: string | null;
  username?: string | null;
}

export function buildReportPdf(report: Report, author: ReportAuthor = {}): jsPDF {
  const doc = new jsPDF({ unit: "mm", format: "a4", compress: true });
  const content = (report.content ?? {}) as Record<string, unknown>;
  const rowsOf = (key: string): Record<string, unknown>[] => {
    const v = content[key];
    return Array.isArray(v) ? (v as Record<string, unknown>[]) : [];
  };

  let y = MARGIN;

  const rgb = (c: RGB): void => {
    doc.setTextColor(c[0], c[1], c[2]);
  };
  const fill = (c: RGB): void => {
    doc.setFillColor(c[0], c[1], c[2]);
  };
  const ensure = (h: number): void => {
    if (y + h > BOTTOM) {
      doc.addPage();
      y = MARGIN;
    }
  };
  const lineH = (size: number): number => size * 0.53 + 0.4;
  const gap = (h: number): void => {
    y += h;
  };

  /** Wrapped paragraph; returns the vertical space consumed. */
  const paragraph = (
    text: string,
    opts: { size?: number; color?: RGB; indent?: number; spaceAfter?: number; style?: "normal" | "bold" } = {},
  ): number => {
    const size = opts.size ?? 10;
    const indent = opts.indent ?? 0;
    doc.setFont("helvetica", opts.style ?? "normal");
    doc.setFontSize(size);
    rgb(opts.color ?? INK);
    const lines = doc.splitTextToSize(pdfText(text), CONTENT_W - indent) as string[];
    const lh = lineH(size);
    const before = y;
    for (const line of lines) {
      ensure(lh);
      doc.text(line, MARGIN + indent, y);
      y += lh;
    }
    y += opts.spaceAfter ?? 0;
    return y - before;
  };

  /** Section heading: violet marker, bold title, optional item count. */
  const heading = (title: string, count?: number): void => {
    ensure(18);
    gap(5);
    fill(VIOLET);
    doc.rect(MARGIN, y - 4, 2.4, 5.8, "F");
    doc.setFont("helvetica", "bold");
    doc.setFontSize(12.5);
    rgb(INK);
    doc.text(pdfText(title), MARGIN + 5.4, y);
    if (count !== undefined) {
      doc.setFont("helvetica", "normal");
      doc.setFontSize(9);
      rgb(MUTED);
      doc.text(`${count} item${count === 1 ? "" : "s"}`, PAGE_W - MARGIN, y, { align: "right" });
    }
    gap(7);
  };

  /** Two-column metadata row: small caps label + value (optionally mono). */
  const kv = (label: string, value: string, mono = false): void => {
    doc.setFont(mono ? "courier" : "helvetica", "normal");
    doc.setFontSize(mono ? 8.4 : 9.6);
    const valueLines = doc.splitTextToSize(pdfText(value), CONTENT_W - 44) as string[];
    const lh = 4.8;
    ensure(valueLines.length * lh + 1.8);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(8);
    rgb(MUTED);
    doc.text(label.toUpperCase(), MARGIN, y, { charSpace: 0.5 });
    doc.setFont(mono ? "courier" : "helvetica", "normal");
    doc.setFontSize(mono ? 8.4 : 9.6);
    rgb(INK);
    valueLines.forEach((line, i) => {
      doc.text(line, MARGIN + 44, y);
      if (i < valueLines.length - 1) y += lh;
    });
    gap(lh + 1.8);
  };

  /** The report's particulars — name, email, username, hypothesis — in one box. */
  const particularsBox = (who: ReportAuthor, hypothesis: string): void => {
    const rows: [string, string][] = [
      ["Name", who.name || "—"],
      ["Email", who.email || "—"],
      ["Username", who.username || "—"],
    ];
    doc.setFont("helvetica", "normal");
    doc.setFontSize(10);
    const hypLines = hypothesis
      ? (doc.splitTextToSize(pdfText(hypothesis), CONTENT_W - 24) as string[])
      : [];
    const rowLh = 5.8;
    const hypLh = lineH(10);
    // Height: padding + title + three rows (+ hypothesis label and lines) + padding.
    const h =
      13 +
      rows.length * rowLh +
      (hypLines.length > 0 ? 6.2 + hypLines.length * hypLh : 0);
    ensure(h);
    fill(SOFT);
    doc.rect(MARGIN, y, CONTENT_W, h, "F");
    fill(VIOLET);
    doc.rect(MARGIN, y, 2.4, h, "F");

    let cy = y + 7.4;
    doc.setFont("helvetica", "bold");
    doc.setFontSize(8.4);
    rgb(VIOLET_DEEP);
    doc.text("REPORT PARTICULARS", MARGIN + 7, cy, { charSpace: 0.6 });
    cy += 4.4;

    for (const [label, value] of rows) {
      doc.setFont("helvetica", "bold");
      doc.setFontSize(8.4);
      rgb(MUTED);
      doc.text(label.toUpperCase(), MARGIN + 7, cy, { charSpace: 0.5 });
      doc.setFont("helvetica", "normal");
      doc.setFontSize(10);
      rgb(INK);
      doc.text(pdfText(value), MARGIN + 46, cy);
      cy += rowLh;
    }
    if (hypLines.length > 0) {
      cy += 1.6;
      doc.setFont("helvetica", "bold");
      doc.setFontSize(8.4);
      rgb(VIOLET_DEEP);
      doc.text("HYPOTHESIS — NOT A CONCLUSION", MARGIN + 7, cy, { charSpace: 0.6 });
      cy += 4.4;
      doc.setFont("helvetica", "normal");
      doc.setFontSize(10);
      rgb(INK);
      for (const line of hypLines) {
        doc.text(line, MARGIN + 7, cy);
        cy += hypLh;
      }
    }
    y += h + 4;
  };

  /** Numbered finding, matching the Findings tab's 01/02/03 references. */
  const findingItem = (n: number, summary: string, meta: string): void => {
    const size = 10;
    doc.setFont("helvetica", "normal");
    doc.setFontSize(size);
    const lines = doc.splitTextToSize(pdfText(summary), CONTENT_W - 14) as string[];
    doc.setFont("courier", "normal");
    doc.setFontSize(8.4);
    const metaLines = doc.splitTextToSize(pdfText(meta), CONTENT_W - 14) as string[];
    const lh = lineH(size);
    ensure(Math.min(lines.length * lh + metaLines.length * 4.6 + 3, 45));
    doc.setFont("courier", "bold");
    doc.setFontSize(9.5);
    rgb(VIOLET);
    doc.text(String(n).padStart(2, "0"), MARGIN, y);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(size);
    rgb(INK);
    for (const line of lines) {
      ensure(lh);
      doc.text(line, MARGIN + 14, y);
      y += lh;
    }
    if (metaLines.length > 0) {
      doc.setFont("courier", "normal");
      doc.setFontSize(8.4);
      rgb(MUTED);
      for (const line of metaLines) {
        ensure(4.6);
        doc.text(line, MARGIN + 14, y);
        y += 4.6;
      }
    }
    gap(3.2);
  };

  /* ---------------------------------------------------------- cover band -- */
  fill(VIOLET);
  doc.rect(0, 0, PAGE_W, 30, "F");
  fill(VIOLET_DEEP);
  doc.rect(0, 30, PAGE_W, 3.4, "F");
  doc.setTextColor(255, 255, 255);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(19);
  doc.text("TraceGuard AI", MARGIN, 15.5);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9.2);
  doc.text("INVESTIGATION REPORT", MARGIN, 23, { charSpace: 1.6 });
  doc.setFont("helvetica", "bold");
  doc.setFontSize(10);
  doc.text(titleCase(report.status).toUpperCase(), PAGE_W - MARGIN, 15.5, {
    align: "right",
    charSpace: 1.2,
  });
  doc.setFont("helvetica", "normal");
  doc.setFontSize(8.6);
  doc.text(`Run ${report.run_id.slice(0, 8)}`, PAGE_W - MARGIN, 22.5, { align: "right" });
  y = 44;

  /* --------------------------------------------------------- particulars -- */
  particularsBox(author, String(content.hypothesis ?? ""));

  /* ------------------------------------------------------------ metadata -- */
  kv("Report ID", report.id, true);
  kv("Run ID", report.run_id, true);
  if (content.case_id) kv("Case", String(content.case_id), true);
  kv("Status", titleCase(report.status));
  kv("Generated", formatDateTime(report.created_at));
  if (report.approved_by) {
    kv(
      "Approved",
      `${report.approved_by}${report.approved_at ? ` · ${formatDateTime(report.approved_at)}` : ""}`,
    );
  }
  if (report.content_hash) kv("Content hash", report.content_hash, true);

  // Status stamp — draft vs approved is impossible to miss in print.
  const stamp =
    report.status === "approved"
      ? "APPROVED — content hash recorded in the audit log"
      : report.status === "draft"
        ? "DRAFT — awaiting human review"
        : titleCase(report.status).toUpperCase();
  const stampColor: RGB = report.status === "approved" ? GREEN : report.status === "draft" ? AMBER : MUTED;
  ensure(14);
  gap(3);
  doc.setDrawColor(stampColor[0], stampColor[1], stampColor[2]);
  doc.setLineWidth(0.4);
  doc.rect(MARGIN, y, CONTENT_W, 10.5, "S");
  doc.setFont("helvetica", "bold");
  doc.setFontSize(8.8);
  rgb(stampColor);
  doc.text(stamp, PAGE_W / 2, y + 6.6, { align: "center", charSpace: 0.4 });
  gap(15);

  /* ------------------------------------------------------------- findings -- */
  // Point-wise: every bucket in one numbered list, strongest evidence first.
  const orderedFindings = EPISTEMIC_ORDER.flatMap((group) =>
    rowsOf(group.key).map((row) => ({ row, group })),
  );
  if (orderedFindings.length > 0) {
    heading("Findings", orderedFindings.length);
    orderedFindings.forEach(({ row, group }, i) => {
      const meta = [
        titleCase(group.status),
        row.claim_type ? titleCase(String(row.claim_type)) : null,
        row.agent ? `Agent: ${titleCase(String(row.agent))}` : null,
        row.flagged_uncited === true ? "FLAGGED: UNCITED" : null,
      ]
        .filter(Boolean)
        .join(" · ");
      findingItem(i + 1, String(row.summary ?? ""), meta);
    });
  }

  /* ------------------------------------------------------------- defence -- */
  // Counter-arguments: contradictions and alternatives, point-wise.
  const defence = rowsOf("contradictions");
  if (defence.length > 0) {
    heading("Defence", defence.length);
    defence.forEach((c, i) => {
      const kind = String(c.kind ?? "").replace(/_/g, " ");
      ensure(16);
      const tone: RGB =
        kind === "verified contradiction" ? RED : kind === "plausible alternative" ? AMBER : VIOLET;
      doc.setFont("courier", "bold");
      doc.setFontSize(9.5);
      rgb(VIOLET);
      doc.text(String(i + 1).padStart(2, "0"), MARGIN, y);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(8.6);
      rgb(tone);
      doc.text(kind.toUpperCase(), MARGIN + 14, y, { charSpace: 0.5 });
      gap(5.6);
      paragraph(String(c.description ?? ""), { indent: 14 });
      if (c.basis) {
        paragraph(`Basis: ${String(c.basis)}`, { size: 9.2, color: MUTED, indent: 14, spaceAfter: 1 });
      }
      gap(3);
    });
  }

  /* -------------------------------------------------------------- footers -- */
  const pages = doc.getNumberOfPages();
  for (let p = 1; p <= pages; p++) {
    doc.setPage(p);
    const fy = PAGE_H - 13;
    doc.setDrawColor(RULE[0], RULE[1], RULE[2]);
    doc.setLineWidth(0.2);
    doc.line(MARGIN, fy - 4.6, PAGE_W - MARGIN, fy - 4.6);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(7.4);
    rgb(MUTED);
    doc.text(
      "TraceGuard AI · Human-supervised, not an autonomous decision-maker.",
      MARGIN,
      fy,
    );
    doc.text(
      `Report ${report.id.slice(0, 8)} · Page ${p} of ${pages}`,
      PAGE_W - MARGIN,
      fy,
      { align: "right" },
    );
  }

  return doc;
}

/** Render the report and trigger a .pdf download in the browser. */
export function downloadReportPdf(report: Report, author?: ReportAuthor): void {
  const doc = buildReportPdf(report, author);
  const stamp = new Date().toISOString().slice(0, 10);
  const run = report.run_id.slice(0, 8);
  doc.save(`traceguard-report-${run}-${stamp}.pdf`);
}

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import {
  cancelInvestigation,
  generateReport,
  getConfidence,
  getContradictions,
  getFindings,
  getInvestigation,
  getInvestigationTimeline,
  getReport,
} from "../api/endpoints";
import { toApiError } from "../api/client";
import { toast } from "../state/toast";
import { useAuth } from "../state/auth";
import {
  Button,
  Card,
  EmptyState,
  ErrorBanner,
  Loading,
  Note,
  PageHeader,
  Pill,
  Skeleton,
  Stat,
  StatusPill,
  Tabs,
} from "../components/common";
import { StatusChip } from "../components/StatusChip";
import type { EpistemicStatus, Finding, InvestigationStatus } from "../api/types";
import {
  IconActivity,
  IconAlert,
  IconArrowLeft,
  IconClock,
  IconDownload,
  IconFile,
  IconGrid,
  IconInfo,
  IconLayers,
  IconShield,
  IconTarget,
} from "../components/icons";
import { formatDuration, formatDateTime, titleCase } from "../utils/format";
import { EPISTEMIC_ORDER, findingMeta, orderFindings } from "../utils/epistemic";
import { downloadReportPdf } from "../utils/reportPdf";

const TABS = ["Status", "Findings", "Defense", "Confidence", "Timeline", "Report"] as const;
type Tab = (typeof TABS)[number];

const TERMINAL = ["approved", "failed", "cancelled"];

// Ordered pipeline as implemented by the orchestrator (used for progress UI).
const PHASES: { id: string; label: string }[] = [
  { id: "validating", label: "Validate" },
  { id: "hashing", label: "Hash" },
  { id: "planning", label: "Plan" },
  { id: "agents_running", label: "Agents" },
  { id: "normalizing", label: "Normalize" },
  { id: "graphing", label: "Graph" },
  { id: "timeline", label: "Timeline" },
  { id: "defense", label: "Defense" },
  { id: "confidence", label: "Confidence" },
  { id: "report_draft", label: "Report" },
  { id: "awaiting_review", label: "Review" },
];

export function InvestigationPage() {
  const { investigationId = "" } = useParams();
  const [tab, setTab] = useState<Tab>("Status");

  // Poll status while the run is in progress.
  const statusQuery = useQuery({
    queryKey: ["investigation", investigationId],
    queryFn: () => getInvestigation(investigationId),
    refetchInterval: (q) =>
      q.state.data && TERMINAL.concat("awaiting_review").includes(q.state.data.status)
        ? false
        : 2000,
  });

  const run = statusQuery.data;

  return (
    <>
      <Link
        to={`/app/cases/${run?.case_id ?? ""}`}
        className="tg-back-link"
      >
        <IconArrowLeft size={15} /> Back to case
      </Link>

      <PageHeader
        title="Investigation"
        subtitle={
          run
            ? `Run ${run.id.slice(0, 8)} · started ${formatDateTime(run.started_at)}`
            : "Loading investigation…"
        }
        actions={run && <StatusPill value={run.status} />}
      />

      {run && <PipelineStrip run={run} />}

      <Tabs
        ariaLabel="Investigation sections"
        active={tab}
        onChange={(t) => setTab(t as Tab)}
        tabs={[
          { id: "Status", label: "Status" },
          { id: "Findings", label: "Findings", count: run?.findings_count },
          { id: "Defense", label: "Defense", count: run?.contradictions_count },
          { id: "Confidence", label: "Confidence" },
          { id: "Timeline", label: "Timeline", count: run?.timeline_count },
          { id: "Report", label: "Report" },
        ]}
      />

      {statusQuery.isLoading && (
        <Card tone="violet">
          {/* Shimmering placeholder instead of a static "Loading…" line. */}
          <div className="tg-run-skeleton" role="status" aria-live="polite">
            <span className="tg-run-skeleton-row">
              <Skeleton width="150px" height={16} />
              <Skeleton width="96px" height={16} />
            </span>
            <Skeleton width="100%" height={8} />
            <Skeleton width="94%" height={8} />
            <Skeleton width="81%" height={8} />
            <Skeleton width="66%" height={8} />
            <span className="tg-run-skeleton-row">
              <Skeleton width="120px" height={14} />
              <Skeleton width="70px" height={14} />
            </span>
          </div>
        </Card>
      )}
      {statusQuery.isError && <ErrorBanner message="Investigation not found." />}

      {run && (
        <>
          {tab === "Status" && <StatusTab id={investigationId} />}
          {tab === "Findings" && <FindingsTab id={investigationId} />}
          {tab === "Defense" && <DefenseTab id={investigationId} />}
          {tab === "Confidence" && <ConfidenceTab id={investigationId} />}
          {tab === "Timeline" && <TimelineTab id={investigationId} />}
          {tab === "Report" && <ReportTab id={investigationId} />}
        </>
      )}
    </>
  );
}

/* ------------------------------------------------------------ Progress ---- */

type PipelineInfo = {
  /** Index of the phase the run currently sits on. */
  current: number;
  /** Completed share of the pipeline, 0–100. */
  filled: number;
  failed: boolean;
  allDone: boolean;
  /** True while the automatic phases are still executing. */
  inFlight: boolean;
};

function pipelineProgress(status: string): PipelineInfo {
  const failed = status === "failed" || status === "cancelled";
  const allDone = status === "approved";
  const idx = PHASES.findIndex((p) => p.id === status);
  const current = allDone ? PHASES.length - 1 : idx < 0 ? 0 : idx;
  const filled = allDone ? 100 : Math.round((current / PHASES.length) * 100);
  const inFlight = !failed && !allDone && status !== "awaiting_review";
  return { current, filled, failed, allDone, inFlight };
}

/** Ticking clock so elapsed time (and the live dot) never look frozen. */
function useTicker(active: boolean, intervalMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    setNow(Date.now());
    const id = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(id);
  }, [active, intervalMs]);
  return now;
}

function elapsedLabel(
  run: Pick<InvestigationStatus, "started_at" | "completed_at">,
  now: number,
): string {
  const start = Date.parse(run.started_at);
  if (Number.isNaN(start)) return "—";
  const end = run.completed_at ? Date.parse(run.completed_at) : now;
  return formatDuration(Math.max(0, (Number.isNaN(end) ? now : end) - start));
}

/**
 * Always-visible progress strip under the page header: live dot, phase counter,
 * animated fill and a running elapsed clock. Rendered on every tab so the run
 * never looks static, even while another section is open.
 */
function PipelineStrip({ run }: { run: InvestigationStatus }) {
  const { current, filled, failed, allDone, inFlight } = pipelineProgress(run.status);
  const now = useTicker(inFlight);
  const phase = PHASES[current];
  const label = failed
    ? "Stopped"
    : allDone
      ? "Complete"
      : `Phase ${current + 1} of ${PHASES.length} · ${phase.label}`;

  return (
    <div className="tg-pipeline-strip" role="status" aria-live="polite">
      <span className="tg-pipeline-strip-title">
        <span
          className="tg-live-dot"
          data-state={failed ? "stopped" : inFlight ? "running" : "idle"}
          aria-hidden="true"
        />
        {label}
      </span>
      <span className="tg-pipeline-strip-track" aria-hidden="true">
        <span
          className="tg-pipeline-fill"
          data-state={failed ? "error" : allDone ? "done" : "running"}
          style={{ width: `${filled}%` }}
        />
        {inFlight && (
          <span
            className="tg-pipeline-active"
            style={{ left: `${filled}%`, width: `${Math.max(8, 100 - filled)}%` }}
          />
        )}
      </span>
      <span className="tg-pipeline-pct">{filled}%</span>
      <span className="tg-pipeline-elapsed">{elapsedLabel(run, now)}</span>
    </div>
  );
}

function ProgressRail({ run }: { run: InvestigationStatus }) {
  const { current, failed, allDone } = pipelineProgress(run.status);

  return (
    <ol className="tg-phases">
      {PHASES.map((p, i) => {
        const state = failed
          ? i < current
            ? "done"
            : i === current
              ? "failed"
              : "todo"
          : allDone || i < current
            ? "done"
            : i === current
              ? "now"
              : "todo";
        const meta =
          state === "done"
            ? "Complete"
            : state === "failed"
              ? "Stopped"
              : state === "now"
                ? run.status === "created"
                  ? "Queued"
                  : "Running…"
                : "Pending";
        return (
          <li key={p.id} className="tg-phase" data-state={state}>
            <span className="tg-phase-dot" aria-hidden="true">
              {state === "done" ? "✓" : state === "failed" ? "✕" : state === "now" ? "▸" : i + 1}
            </span>
            <span className="tg-phase-label">{p.label}</span>
            <span className="tg-phase-meta">{meta}</span>
          </li>
        );
      })}
    </ol>
  );
}

/* -------------------------------------------------------------- Status ---- */

function StatusTab({ id }: { id: string }) {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["investigation", id], queryFn: () => getInvestigation(id) });
  const cancelMut = useMutation({
    mutationFn: () => cancelInvestigation(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["investigation", id] });
      toast.info("Investigation cancelled", "Partial findings are kept for review.");
    },
    onError: (err) => toast.error("Could not cancel", toApiError(err).message),
  });
  if (!data) return <Loading />;

  const isActive = !TERMINAL.includes(data.status) && data.status !== "awaiting_review";

  return (
    <>
      <Card
        title="Workflow status"
        tone="blue"
        icon={<IconActivity size={16} />}
        actions={<StatusPill value={data.status} />}
      >
        <div className="tg-grid tg-grid-4" style={{ marginBottom: "var(--tg-space-5)" }}>
          <Stat label="Findings" tone="violet" value={data.findings_count} icon={<IconTarget size={22} />} />
          <Stat
            label="Contradictions"
            tone="blue"
            value={data.contradictions_count}
            icon={<IconShield size={22} />}
          />
          <Stat
            label="Confidence"
            tone="cyan"
            value={data.confidence_band ? titleCase(data.confidence_band) : "—"}
            icon={<IconLayers size={22} />}
            hint="Ordinal band, not a probability"
          />
          <Stat label="Timeline events" tone="slate" value={data.timeline_count} icon={<IconClock size={22} />} />
        </div>

        {data.hypothesis && (
          <Note icon={<IconInfo size={16} />}>
            <strong>Working hypothesis (not a conclusion):</strong> {data.hypothesis}
          </Note>
        )}

        {data.errors.length > 0 && (
          <div className="tg-mt-4">
            <ErrorBanner
              message={data.errors
                .map((e) => `${String(e.node ?? "step")}: ${String(e.message ?? "")}`)
                .join(" · ")}
            />
          </div>
        )}

        {isActive && (
          <div className="tg-mt-4">
            <Button variant="danger" onClick={() => cancelMut.mutate()} disabled={cancelMut.isPending}>
              {cancelMut.isPending ? "Cancelling…" : "Cancel investigation"}
            </Button>
          </div>
        )}
      </Card>

      <div className="tg-grid tg-grid-2">
        <Card
          title="Pipeline"
          tone="cyan"
          subtitle="Automatic phases, in order"
          icon={<IconGrid size={16} />}
          actions={
            <span className="tg-pill tg-pill-info">
              {pipelineProgress(data.status).filled}%
            </span>
          }
        >
          <ProgressRail run={data} />
        </Card>

        <Card
          title="Agent executions"
          tone="slate"
          icon={<IconLayers size={16} />}
          actions={<span className="tg-pill">{data.agent_executions.length}</span>}
        >
          {data.agent_executions.length === 0 ? (
            <EmptyState
              icon={<IconGrid size={22} />}
              title="No executions yet"
              message="Agents will appear here as the pipeline reaches the analysis phase."
            />
          ) : (
            <ul className="tg-list">
              {data.agent_executions.map((e, i) => (
                <li key={i} className="tg-list-item">
                  <div className="tg-list-row">
                    <div className="tg-row">
                      <span
                        aria-hidden="true"
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          justifyContent: "center",
                          width: 30,
                          height: 30,
                          borderRadius: 8,
                          background: "var(--tg-surface-3)",
                          color: "var(--tg-cyan)",
                        }}
                      >
                        <IconGrid size={16} />
                      </span>
                      <div>
                        <div className="tg-list-title">{titleCase(e.agent_name)}</div>
                        <div className="tg-list-meta">
                          {e.duration_ms != null ? formatDuration(e.duration_ms) : "—"}
                          {e.error && e.error.message ? ` · ${String(e.error.message)}` : ""}
                        </div>
                      </div>
                    </div>
                    <StatusPill value={e.status} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {data.errors.length > 0 && (
        <Card title="Recorded issues" tone="violet" icon={<IconAlert size={16} />}>
          <ul className="tg-list">
            {data.errors.map((er, i) => (
              <li key={i} className="tg-list-item">
                <code className="tg-break">{JSON.stringify(er)}</code>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}

/* ------------------------------------------------------------ Findings ---- */

function FindingsTab({ id }: { id: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["findings", id],
    queryFn: () => getFindings(id),
  });
  if (isLoading) return <Loading label="Loading findings…" />;
  if (!data || data.length === 0)
    return (
      <Card tone="blue">
        <EmptyState
          icon={<IconTarget size={22} />}
          title="No findings yet"
          //message="Findings appear once the agent pipeline has run over this case's evidence."
          steps={[
            {
              label: "Let the run complete",
              //detail: "Content extraction → OSINT → metadata → crypto, in that order",
            },
            {
              label: "Check Status for recorded issues",
              //detail: "Failed or skipped steps are listed there, never hidden",
            },
          ]} message={""}        />
      </Card>
    );

  // Reading order: strongest evidence first, then oldest event first —
  // the same sequence a reviewer would cite in, e.g., finding 03.
  const ordered = orderFindings(data);

  type Section = {
    key: string;
    status: EpistemicStatus | null;
    label: string;
    blurb: string;
    items: { n: number; finding: Finding }[];
  };
  let counter = 0;
  const sections: Section[] = [];
  for (const group of EPISTEMIC_ORDER) {
    const items = ordered.filter((f) => f.epistemic_status === group.status);
    if (items.length === 0) continue;
    sections.push({
      key: group.key,
      status: group.status,
      label: group.label,
      blurb: group.blurb,
      items: items.map((finding) => ({ n: ++counter, finding })),
    });
  }
  // Statuses outside the canonical set still surface — never hidden.
  const rest = ordered.filter((f) => !EPISTEMIC_ORDER.some((g) => g.status === f.epistemic_status));
  if (rest.length > 0) {
    sections.push({
      key: "other",
      status: null,
      label: "Other",
      blurb: "Epistemic status outside the standard set — review individually.",
      items: rest.map((finding) => ({ n: ++counter, finding })),
    });
  }

  return (
    <Card
      title="Findings explorer"
      tone="cyan"
      icon={<IconTarget size={16} />}
      subtitle={`${data.length} finding${data.length === 1 ? "" : "s"} · strongest evidence first, then oldest event first`}
      bodyClassName="tg-flush"
    >
      <div className="tg-findings">
        {sections.map((section) => (
          <section key={section.key} className="tg-findings-group" aria-label={section.label}>
            <header className="tg-findings-head">
              {section.status ? (
                <StatusChip status={section.status} />
              ) : (
                <Pill tone="neutral">{section.label}</Pill>
              )}
              <span className="tg-findings-blurb">{section.blurb}</span>
              <span className="tg-pill">{section.items.length}</span>
            </header>
            <ol className="tg-findings-list">
              {section.items.map(({ n, finding }) => (
                <li key={n} className="tg-findings-item">
                  <span className="tg-findings-num" aria-hidden="true">
                    {String(n).padStart(2, "0")}
                  </span>
                  <div className="tg-grow" style={{ minWidth: 0 }}>
                    <div className="tg-list-title tg-break">
                      {String(finding.payload.summary ?? finding.claim_type ?? "finding")}
                    </div>
                    <div className="tg-list-meta">{findingMeta(finding)}</div>
                  </div>
                </li>
              ))}
            </ol>
          </section>
        ))}
      </div>
    </Card>
  );
}

/* -------------------------------------------------------------- Defense --- */

function DefenseTab({ id }: { id: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["contradictions", id],
    queryFn: () => getContradictions(id),
  });
  if (isLoading) return <Loading label="Loading defence analysis…" />;

  return (
    <Card
      title="Defense agent"
      tone="slate"
      icon={<IconShield size={16} />}
      //subtitle="Challenges the hypothesis with contradictions, alternatives, and open questions."
    >

      {!data || data.length === 0 ? (
        <EmptyState
          icon={<IconShield size={22} />}
          title="Nothing recorded yet" message={""}          //message="No contradictions, alternatives, or open questions have been raised for this run."
        />
      ) : (
        <div className="tg-stack tg-mt-4">
          {data.map((c, i) => {
            const tone =
              c.kind === "verified_contradiction"
                ? "error"
                : c.kind === "plausible_alternative"
                  ? "warning"
                  : "info";
            return (
              <article
                key={i}
                style={{
                  padding: "var(--tg-space-4)",
                  border: "1px solid var(--tg-border)",
                  borderRadius: "var(--tg-radius)",
                  background: "var(--tg-bg-elev)",
                }}
              >
                <div className="tg-row tg-wrap" style={{ marginBottom: 6 }}>
                  <Pill tone={tone}>{String(c.kind).replace(/_/g, " ")}</Pill>
                </div>
                <div className="tg-list-title tg-break">{c.description}</div>
                {c.basis && <div className="tg-list-meta">Basis: {c.basis}</div>}
              </article>
            );
          })}
        </div>
      )}
    </Card>
  );
}

/* ---------------------------------------------------------- Confidence ---- */

function ConfidenceTab({ id }: { id: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["confidence", id],
    queryFn: () => getConfidence(id),
  });
  if (isLoading) return <Loading label="Loading confidence…" />;
  if (!data)
    return (
      <Card tone="violet">
        <EmptyState
          title="No confidence assessment yet"
          message="Confidence is computed after the defence phase completes."
        />
      </Card>
    );

  return (
    <>
      <Card
        title="Confidence assessment"
        tone="blue"
        icon={<IconLayers size={16} />}
        actions={
          <span className="tg-pill tg-pill-info">{titleCase(data.band)} band</span>
        }
      >
        <div className="tg-row tg-wrap" style={{ marginBottom: "var(--tg-space-4)" }}>
          <Stat
            label="Band"
            tone="violet"
            value={titleCase(data.band)}
            icon={<IconTarget size={22} />}
            hint="Heuristic ordinal, not a calibrated probability"
          />
          {data.score != null && (
            <Stat label="Score" tone="blue" value={data.score} icon={<IconLayers size={22} />} />
          )}
        </div>

        <div style={{ marginBottom: "var(--tg-space-5)" }}>
          {Object.entries(data.factors).map(([name, f]) => (
            <div key={name} className="tg-factor">
              <div className="tg-factor-head">
                <span className="tg-factor-name">{titleCase(name)}</span>
                <span className="tg-factor-value">
                  {f.value} × {f.weight}
                </span>
              </div>
              <div className="tg-factor-bar">
                <div className="tg-factor-fill" style={{ width: `${f.value * 100}%` }} />
              </div>
              <div className="tg-factor-rationale">{f.rationale}</div>
            </div>
          ))}
        </div>
      </Card>

      <Card title="IBM Z supplementary score" tone="cyan" icon={<IconLayers size={16} />}>
        {data.ibmz ? (
          <>
            <div className="tg-row tg-wrap">
              {data.ibmz.simulated && <span className="tg-badge-sim">SIMULATED IBM Z</span>}
              {data.ibmz.available ? (
                <Pill tone="success">Score: {data.ibmz.score}</Pill>
              ) : (
                <Pill tone="neutral">Unavailable</Pill>
              )}
            </div>
            <p className="tg-subtle tg-mt-4 tg-mb-0">{data.ibmz.detail}</p>
          </>
        ) : (
          <EmptyState message="No IBM Z score attached." />
        )}
      </Card>

      {data.limitations.length > 0 && (
        <Card title="Limitations" tone="slate" icon={<IconInfo size={16} />}>
          <ul className="tg-list">
            {data.limitations.map((l, i) => (
              <li key={i} className="tg-list-item">
                <span className="tg-break">{l}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}

/* ------------------------------------------------------------- Timeline --- */

function TimelineTab({ id }: { id: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["inv-timeline", id],
    queryFn: () => getInvestigationTimeline(id),
  });
  if (isLoading) return <Loading label="Loading timeline…" />;
  if (!data || data.length === 0)
    return (
      <Card tone="violet">
        <EmptyState icon={<IconClock size={22} />} title="No timeline events" message="Nothing has been ordered in time yet." />
      </Card>
    );

  return (
    <Card title="Chronological timeline" tone="blue" icon={<IconClock size={16} />}>
      <ol className="tg-timeline">
        {data.map((ev, i) => (
          <li key={i} className="tg-timeline-item">
            <span className="tg-timeline-dot" aria-hidden="true" />
            <div className="tg-timeline-time">{ev.at}</div>
            <div className="tg-timeline-label">
              {ev.label ?? "event"}{" "}
              {ev.source && <Pill tone="neutral">{ev.source}</Pill>}
            </div>
          </li>
        ))}
      </ol>
    </Card>
  );
}

/* --------------------------------------------------------------- Report --- */

function ReportTab({ id }: { id: string }) {
  const qc = useQueryClient();
  const { user } = useAuth();
  const [reportId, setReportId] = useState<string | null>(null);
  const genMut = useMutation({
    mutationFn: () => generateReport(id),
    onSuccess: (r) => {
      setReportId(r.id);
      void qc.invalidateQueries({ queryKey: ["report", r.id] });
      toast.success("Draft report generated", "Review it before approval.");
    },
    onError: (err) => toast.error("Report generation failed", toApiError(err).message),
  });
  // Content for the PDF as soon as the report id is known; the review page
  // shares this cache entry, so opening it later is instant.
  const reportQuery = useQuery({
    queryKey: ["report", reportId],
    queryFn: () => getReport(reportId as string),
    enabled: Boolean(reportId),
  });

  return (
    <Card title="Report" tone="cyan" icon={<IconFile size={16} />} subtitle="Draft → human review → approval">
      <Button
        variant="primary"
        onClick={() => genMut.mutate()}
        disabled={genMut.isPending}
        icon={<IconFile size={16} />}
      >
        {genMut.isPending ? "Generating…" : "Generate draft report"}
      </Button>
      {reportId && (
        <div className="tg-row tg-wrap tg-mt-4">
          <Link className="tg-button" to={`/app/reports/${reportId}`}>
            Open report for review →
          </Link>
          <Button
            icon={<IconDownload size={16} />}
            onClick={() => reportQuery.data && downloadReportPdf(reportQuery.data, user ?? undefined)}
            disabled={!reportQuery.data}
            title="Download the report as a PDF file"
          >
            {reportQuery.data ? "Download PDF" : "Loading report…"}
          </Button>
        </div>
      )}
    </Card>
  );
}

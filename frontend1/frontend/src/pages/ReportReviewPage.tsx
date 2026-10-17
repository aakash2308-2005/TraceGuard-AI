import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { approveReport, getReport } from "../api/endpoints";
import { toApiError } from "../api/client";
import { toast } from "../state/toast";
import { useAuth } from "../state/auth";
import {
  Banner,
  Button,
  Card,
  EmptyState,
  ErrorBanner,
  Loading,
  PageHeader,
  Pill,
  StatusPill,
} from "../components/common";
import { StatusChip } from "../components/StatusChip";
import {
  IconAlert,
  IconArrowLeft,
  IconCheck,
  IconDownload,
  IconFile,
  IconInfo,
  IconLock,
} from "../components/icons";
import { formatDateTime } from "../utils/format";
import { EPISTEMIC_ORDER } from "../utils/epistemic";
import { downloadReportPdf } from "../utils/reportPdf";

export function ReportReviewPage() {
  const { reportId = "" } = useParams();
  const qc = useQueryClient();
  const { user } = useAuth();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["report", reportId],
    queryFn: () => getReport(reportId),
  });

  const approveMut = useMutation({
    mutationFn: () => approveReport(reportId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["report", reportId] });
      toast.success("Report approved", "Content hash written to the append-only audit log.");
    },
    onError: (err) => toast.error("Approval failed", toApiError(err).message),
  });

  if (isLoading)
    return (
      <Card tone="cyan">
        <Loading label="Loading report…" />
      </Card>
    );
  if (isError || !data)
    return (
      <>
        <ErrorBanner message="Report not found." />
        <Link to="/app/cases" className="tg-back-link">
          <IconArrowLeft size={15} /> Back to cases
        </Link>
      </>
    );

  const content = data.content as Record<string, unknown>;
  const section = (key: string): Record<string, unknown>[] =>
    (content[key] as Record<string, unknown>[]) ?? [];
  const isDraft = data.status === "draft";
  const findings = EPISTEMIC_ORDER.flatMap(({ key, status }) =>
    section(key).map((row) => ({ row, status })),
  );
  const defence = section("contradictions");

  return (
    <>
      <Link
        to={`/app/cases/${(content.case_id as string) ?? ""}`}
        className="tg-back-link"
      >
        <IconArrowLeft size={15} /> Back
      </Link>

      <PageHeader
        title="Report review & approval"
        subtitle={`Generated ${formatDateTime(data.created_at)} · run ${data.run_id.slice(0, 8)}`}
        actions={
          <div className="tg-row">
            <Button
              icon={<IconDownload size={16} />}
              onClick={() => downloadReportPdf(data, user ?? undefined)}
              title="Download the report as a PDF file"
            >
              Download PDF
            </Button>
            <StatusPill value={data.status} />
          </div>
        }
      />

      {isDraft ? (
        <Card
          title="Awaiting your review"
          tone="slate"
          icon={<IconLock size={16} />}
        >
          <div className="tg-row tg-wrap">
            <Button
              variant="primary"
              onClick={() => approveMut.mutate()}
              disabled={approveMut.isPending}
              icon={<IconCheck size={16} />}
            >
              {approveMut.isPending ? "Approving…" : "Approve report"}
            </Button>
          </div>
          {approveMut.isError && (
            <div className="tg-mt-4">
              <Banner tone="error">{toApiError(approveMut.error).message}</Banner>
            </div>
          )}
        </Card>
      ) : (
        <Card title="Approved" tone="violet" icon={<IconCheck size={16} />}>
          <Banner tone="success" icon={<IconCheck size={16} />}>
            This report has been approved and finalised.
          </Banner>
          <dl className="tg-kv tg-mt-4">
            <dt>Approved by</dt>
            <dd>{data.approved_by ?? "—"}</dd>
            <dt>Approved at</dt>
            <dd>{formatDateTime(data.approved_at)}</dd>
            <dt>Content hash</dt>
            <dd className="tg-hash">{data.content_hash ?? "—"}</dd>
          </dl>
        </Card>
      )}

      {/* One box: the report's particulars, in signing order. */}
      <Card
        title="Report details"
        tone="violet"
        icon={<IconInfo size={16} />}
        subtitle="Name · Email · Username · Hypothesis"
      >
        <dl className="tg-kv">
          <dt>Name</dt>
          <dd>{user?.name || "—"}</dd>
          <dt>Email</dt>
          <dd>{user?.email || "—"}</dd>
          <dt>Username</dt>
          <dd>{user?.username || "—"}</dd>
          <dt>Hypothesis</dt>
          <dd className="tg-break">
            {content.hypothesis ? String(content.hypothesis) : "—"}
          </dd>
        </dl>
      </Card>

      <Card
        title="Findings"
        tone="cyan"
        icon={<IconFile size={16} />}
        subtitle="Point-wise, strongest evidence first"
        actions={<span className="tg-pill">{findings.length}</span>}
        bodyClassName={findings.length === 0 ? "" : "tg-flush"}
      >
        {findings.length === 0 ? (
          <EmptyState icon={<IconFile size={22} />} message="None recorded." />
        ) : (
          <ul
            className="tg-findings-list"
            style={{ padding: "var(--tg-space-4) var(--tg-space-6)" }}
          >
            {findings.map(({ row, status }, i) => (
              <li key={i} className="tg-findings-item">
                <span className="tg-findings-num" aria-hidden="true">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <div className="tg-grow">
                  <div className="tg-break">{String(row.summary ?? "")}</div>
                  <div className="tg-list-meta">
                    <StatusChip status={status} />
                    {row.claim_type ? <span>· {String(row.claim_type)}</span> : null}
                    {row.agent ? <span>· Agent: {String(row.agent)}</span> : null}
                    {row.flagged_uncited === true && (
                      <span className="tg-badge-sim">FLAGGED: UNCITED</span>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card
        title="Defence"
        tone="slate"
        icon={<IconAlert size={16} />}
        subtitle="Counter-arguments and alternatives on the record"
        actions={<span className="tg-pill">{defence.length}</span>}
        bodyClassName={defence.length === 0 ? "" : "tg-flush"}
      >
        {defence.length === 0 ? (
          <EmptyState icon={<IconAlert size={22} />} message="None recorded." />
        ) : (
          <ul
            className="tg-findings-list"
            style={{ padding: "var(--tg-space-4) var(--tg-space-6)" }}
          >
            {defence.map((c, i) => (
              <li key={i} className="tg-findings-item">
                <span className="tg-findings-num" aria-hidden="true">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <div className="tg-grow">
                  <div className="tg-break">{String(c.description ?? "")}</div>
                  {c.basis ? <div className="tg-list-meta">Basis: {String(c.basis)}</div> : null}
                </div>
                <Pill tone={String(c.kind) === "verified_contradiction" ? "error" : "warning"}>
                  {String(c.kind ?? "").replace(/_/g, " ")}
                </Pill>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}

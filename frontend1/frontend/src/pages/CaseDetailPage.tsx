import { FormEvent, useState } from "react";
import type { ChangeEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import {
  getCase,
  listEvidence,
  listMembers,
  startInvestigation,
  submitIndicator,
  uploadFile,
  verifyEvidence,
} from "../api/endpoints";
import { toApiError } from "../api/client";
import { toast } from "../state/toast";
import { useUi } from "../state/ui";
import type { ExportableIndicator } from "../utils/export";
import {
  Banner,
  Button,
  Card,
  DataTable,
  EmptyState,
  ErrorBanner,
  Field,
  Loading,
  PageHeader,
  Pill,
  Stat,
  StatusPill,
} from "../components/common";
import {
  IconArrowLeft,
  IconCheckCircle,
  IconClock,
  IconFile,
  IconFolder,
  IconGraph,
  IconPlay,
  IconPlus,
  IconScroll,
  IconTarget,
  IconUpload,
  IconUsers,
} from "../components/icons";
import { ExportMenu } from "../components/ExportMenu";
import { StartProgress } from "../components/StartProgress";
import { formatBytes, shortHash, titleCase } from "../utils/format";

const INDICATOR_TYPES = ["username", "email", "domain", "ip", "wallet", "tx_hash"];

export function CaseDetailPage() {
  const { caseId = "" } = useParams();
  const qc = useQueryClient();

  const caseQuery = useQuery({ queryKey: ["case", caseId], queryFn: () => getCase(caseId) });
  const evidenceQuery = useQuery({
    queryKey: ["evidence", caseId],
    queryFn: () => listEvidence(caseId),
  });
  const membersQuery = useQuery({
    queryKey: ["members", caseId],
    queryFn: () => listMembers(caseId),
  });

  const [indType, setIndType] = useState("domain");
  const [indValue, setIndValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [startedId, setStartedId] = useState<string | null>(null);
  const [uploadedName, setUploadedName] = useState<string | null>(null);
  // Animated launch overlay — mirrors the flow on the Investigate page.
  const [launching, setLaunching] = useState(false);

  const invalidateEvidence = () => void qc.invalidateQueries({ queryKey: ["evidence", caseId] });

  const indicatorMut = useMutation({
    mutationFn: () => submitIndicator(caseId, indType, indValue),
    onSuccess: () => {
      const added = indValue.trim();
      setIndValue("");
      setError(null);
      invalidateEvidence();
      toast.success("Indicator added", added);
    },
    onError: (err) => {
      const message = toApiError(err).message;
      setError(message);
      toast.error("Indicator rejected", message);
    },
  });

  const uploadMut = useMutation({
    mutationFn: (file: File) => uploadFile(caseId, file),
    onSuccess: (_ev, file) => {
      setUploadedName(file.name);
      setError(null);
      invalidateEvidence();
      toast.success("Evidence uploaded", file.name);
    },
    onError: (err) => {
      const message = toApiError(err).message;
      setError(message);
      toast.error("Upload failed", message);
    },
  });

  const verifyMut = useMutation({
    mutationFn: (eid: string) => verifyEvidence(caseId, eid),
    onSuccess: invalidateEvidence,
    onError: (err) => toast.error("Verification failed", toApiError(err).message),
  });

  const startMut = useMutation({
    mutationFn: () => startInvestigation(caseId),
    onSuccess: (res) => {
      setStartedId(res.id);
      toast.success("Investigation started", "Agents are running in the background.");
    },
    onError: (err) => {
      const message = toApiError(err).message;
      setError(message);
      toast.error("Could not start investigation", message);
    },
  });

  const onIndicator = (e: FormEvent) => {
    e.preventDefault();
    if (indValue.trim()) indicatorMut.mutate();
  };

  const onFile = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) uploadMut.mutate(file);
    // Allow re-selecting the same file name later.
    e.target.value = "";
  };

  const canWrite = ["lead", "investigator"].includes(caseQuery.data?.my_case_role ?? "");
  const evidence = evidenceQuery.data ?? [];
  const files = evidence.filter((e) => e.type === "file");
  const indicators = evidence.filter((e) => e.type === "indicator");
  const verified = evidence.filter((e) => e.verification_status === "verified").length;

  const openEntity = useUi((s) => s.openEntity);

  /** Indicator rows double as drawer entry points — same shape ExportMenu wants. */
  const exportable: ExportableIndicator[] = indicators
    .filter((ev) => Boolean(ev.indicator_value))
    .map((ev) => ({
      value: ev.indicator_value as string,
      type: (ev.indicator_type ?? "unknown").toLowerCase(),
      status: ev.verification_status,
      first_seen: ev.acquired_at,
    }));

  const evColumns = ["Type", "Value / File", "SHA-256", "Size", "Verification", "Action"];
  const evRows = evidence.map((ev) => [
    <span key={`${ev.id}-t`}>
      {ev.type === "indicator" ? (
        <Pill tone="info">{titleCase(ev.indicator_type ?? "")}</Pill>
      ) : (
        <Pill tone="neutral" dot>
          file
        </Pill>
      )}
    </span>,
    <span key={`${ev.id}-v`} className="tg-break">
      {ev.type === "indicator" ? (
        <button
          type="button"
          className="tg-entity-link"
          title={`${ev.indicator_value} — open detail`}
          onClick={() =>
            openEntity({
              value: ev.indicator_value ?? "",
              kind: titleCase(ev.indicator_type ?? "Indicator"),
              caseId,
              status: ev.verification_status,
            })
          }
        >
          {ev.indicator_value}
        </button>
      ) : (
        ev.original_filename
      )}
    </span>,
    <span key={`${ev.id}-h`} className="tg-hash">
      {shortHash(ev.sha256)}
    </span>,
    <span key={`${ev.id}-s`} className="tg-dim">
      {formatBytes(ev.size_bytes)}
    </span>,
    <StatusPill key={`${ev.id}-vs`} value={ev.verification_status} />,
    ev.type === "file" ? (
      <Button
        key={`${ev.id}-a`}
        size="sm"
        onClick={() => verifyMut.mutate(ev.id)}
        disabled={verifyMut.isPending}
      >
        Verify
      </Button>
    ) : (
      <span className="tg-dim" key={`${ev.id}-a`}>
        —
      </span>
    ),
  ]);

  return (
    <>
      <Link to="/app/cases" className="tg-back-link">
        <IconArrowLeft size={15} /> All cases
      </Link>

      {caseQuery.isLoading && (
        <Card tone="violet">
          <Loading label="Loading case…" />
        </Card>
      )}
      {caseQuery.isError && <ErrorBanner message="Case not found or access denied." />}

      {caseQuery.data && (
        <>
          <PageHeader
            title={caseQuery.data.title}
            subtitle={caseQuery.data.description ?? "No description provided."}
            actions={
              <>
                <StatusPill value={caseQuery.data.status} />
                {caseQuery.data.my_case_role && (
                  <Pill tone="info">Your role: {titleCase(caseQuery.data.my_case_role)}</Pill>
                )}
                <Link className="tg-button tg-button-sm" to={`/app/cases/${caseId}/graph`}>
                  <IconGraph size={15} /> Graph
                </Link>
                <Link className="tg-button tg-button-sm" to={`/app/cases/${caseId}/timeline`}>
                  <IconClock size={15} /> Timeline
                </Link>
                <Link className="tg-button tg-button-sm" to={`/app/cases/${caseId}/audit`}>
                  <IconScroll size={15} /> Audit
                </Link>
                <ExportMenu caseTitle={caseQuery.data.title} indicators={exportable} />
              </>
            }
          />

          <div className="tg-grid tg-grid-4" style={{ marginBottom: "var(--tg-space-5)" }}>
            <Stat label="Evidence items" tone="violet" value={evidence.length} icon={<IconFile size={22} />} />
            <Stat label="Indicators" tone="blue" value={indicators.length} icon={<IconTarget size={22} />} />
            <Stat label="Files" tone="cyan" value={files.length} icon={<IconFolder size={22} />} />
            <Stat
              label="Verified"
              tone="slate"
              value={verified}
              icon={<IconCheckCircle size={22} />}
              hint="Chain-of-custody checked"
            />
          </div>

          <div className="tg-grid tg-grid-3">
            <div className="tg-span-2">
              <Card
                title="Evidence"
                tone="blue"
                icon={<IconFile size={16} />}
                //subtitle="Everything collected for this case."
                bodyClassName="tg-flush"
              >
                {evidenceQuery.isLoading && (
                  <div style={{ padding: "var(--tg-space-6)" }}>
                    <Loading label="Loading evidence…" />
                  </div>
                )}
                {evidenceQuery.data && evidenceQuery.data.length === 0 && (
                  <EmptyState
                    title="No evidence yet"
                    message="Everything the agents will analyse comes from here — indicators you paste and files you upload."
                    steps={[
                      {
                        label: "Paste an indicator",
                        detail: "Domain, IP, email, username, wallet or transaction hash",
                        onClick: () => document.getElementById("indval")?.focus(),
                      },
                      {
                        label: "Upload a file",
                        detail: "Text, PDF and Office files are scanned for identifiers",
                        onClick: () => document.getElementById("dropzone")?.focus(),
                      },
                      {
                        label: "Start the investigation",
                        //detail: "Agents correlate what they find; you review every claim",
                      },
                    ]}
                  />
                )}
                {evidence.length > 0 && <DataTable columns={evColumns} rows={evRows} />}
              </Card>

              <Card title="Add evidence" tone="cyan" icon={<IconPlus size={16} />} subtitle={canWrite ? undefined : "Read-only access"}>
                {!canWrite ? (
                  <EmptyState
                    icon={<IconTarget size={22} />}
                    title="Read-only access"
                    message="You have view-only access to this case. Ask a lead or investigator to grant you write access."
                  />
                ) : (
                  <>
                    <form onSubmit={onIndicator}>
                      <div className="tg-input-row">
                        <Field label="Indicator type" htmlFor="indtype">
                          <select
                            id="indtype"
                            className="tg-select"
                            value={indType}
                            onChange={(e) => setIndType(e.target.value)}
                            style={{ width: "auto", minWidth: 150 }}
                          >
                            {INDICATOR_TYPES.map((t) => (
                              <option key={t} value={t}>
                                {t}
                              </option>
                            ))}
                          </select>
                        </Field>
                        <Field label="Value" htmlFor="indval">
                          <input
                            id="indval"
                            className="tg-input"
                            value={indValue}
                            onChange={(e) => setIndValue(e.target.value)}
                            placeholder={`e.g. ${indType === "email" ? "user@example.com" : "example.com"}`}
                          />
                        </Field>
                        <div className="tg-field">
                          <Button
                            type="submit"
                            variant="primary"
                            disabled={indicatorMut.isPending || !indValue.trim()}
                            icon={<IconPlus size={16} />}
                          >
                            {indicatorMut.isPending ? "Adding…" : "Add indicator"}
                          </Button>
                        </div>
                      </div>
                    </form>

                    <hr className="tg-divider" />

                    {/* The file input itself is display:none, so the label is
                        made focusable and activatable — otherwise the upload
                        control is unreachable from the keyboard. */}
                    <label
                      id="dropzone"
                      className="tg-dropzone"
                      htmlFor="file-input"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          document.getElementById("file-input")?.click();
                        }
                      }}
                    >
                      <span className="tg-dropzone-icon">
                        <IconUpload size={26} />
                      </span>
                      <span className="tg-dropzone-title">
                        {uploadMut.isPending ? "Uploading…" : "Click to upload a file"}
                      </span>
                      <span className="tg-dropzone-sub">
                        Text, CSV, JSON, XML, Markdown, PDF and Office documents
                      </span>
                      <input id="file-input" type="file" onChange={onFile} />
                    </label>
                    <p className="tg-hint">
                      Text, PDF and Office (docx/xlsx/pptx) files are scanned for usernames,
                      emails, IPs and domains when an investigation runs.
                    </p>
                    {uploadMut.isPending && <Loading label="Uploading file…" />}
                    {uploadedName && uploadMut.isSuccess && (
                      <Banner tone="success">
                        Uploaded <strong>{uploadedName}</strong> — it will be included in the next
                        investigation.
                      </Banner>
                    )}
                    {error && <Banner tone="error">{error}</Banner>}
                  </>
                )}
              </Card>
            </div>

            <div>
              <Card title="Run investigation" tone="slate" icon={<IconPlay size={16} />} subtitle="Human-supervised">
                
                {canWrite ? (
                  <>
                    <Button
                      variant="primary"
                      fullWidth
                      size="lg"
                      onClick={() => {
                        if (startMut.isPending) return;
                        startMut.reset();
                        setLaunching(true);
                        startMut.mutate();
                      }}
                      disabled={startMut.isPending}
                      icon={<IconPlay size={16} />}
                    >
                      {startMut.isPending ? "Starting…" : "Start investigation"}
                    </Button>
                    {startedId && (
                      <div className="tg-mt-4">
                        <Link
                          className="tg-button tg-button-full tg-live-status-link"
                          to={`/app/investigations/${startedId}`}
                        >
                          Open live status →
                        </Link>
                      </div>
                    )}
                    {evidence.length === 0 && (
                      <p className="tg-hint">Add at least one evidence item before running.</p>
                    )}
                  </>
                ) : (
                  <EmptyState
                    title="Write access required"
                    message="Only case leads and investigators can start an investigation."
                  />
                )}
                <div className="tg-mt-4">
                  
                </div>
              </Card>

              <Card
                title="Members"
                tone="violet"
                icon={<IconUsers size={16} />}
                actions={<span className="tg-pill">{membersQuery.data?.length ?? 0}</span>}
                bodyClassName="tg-flush"
              >
                {membersQuery.data && membersQuery.data.length > 0 ? (
                  <ul className="tg-list" style={{ padding: "var(--tg-space-4) var(--tg-space-6)" }}>
                    {membersQuery.data.map((m) => (
                      <li key={m.user_id} className="tg-list-item">
                        <div className="tg-list-row">
                          <span className="tg-list-title">{m.username}</span>
                          <Pill tone="info">{titleCase(m.case_role)}</Pill>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <EmptyState icon={<IconUsers size={22} />} message="No members yet." />
                )}
              </Card>

              <Card title="Case resources" tone="blue" icon={<IconScroll size={16} />}>
                <div className="tg-stack-sm">
                  <Link className="tg-button tg-button-full" to={`/app/cases/${caseId}/graph`}>
                    <IconGraph size={16} /> Relationship graph
                  </Link>
                  <Link className="tg-button tg-button-full" to={`/app/cases/${caseId}/timeline`}>
                    <IconClock size={16} /> Case timeline
                  </Link>
                  <Link className="tg-button tg-button-full" to={`/app/cases/${caseId}/audit`}>
                    <IconScroll size={16} /> Audit history
                  </Link>
                </div>
              </Card>
            </div>
          </div>
        </>
      )}

      <StartProgress
        open={launching}
        ready={startMut.isSuccess}
        title="Starting investigation"
        readyDetail="Run is live — open the live status view whenever you're ready."
        error={startMut.isError ? toApiError(startMut.error).message : null}
        onComplete={() => setLaunching(false)}
        onClose={() => {
          setLaunching(false);
          startMut.reset();
        }}
      />
    </>
  );
}

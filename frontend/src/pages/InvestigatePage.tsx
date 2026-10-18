import { FormEvent, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { createCase, submitIndicator, uploadFile, startInvestigation } from "../api/endpoints";
import { toApiError } from "../api/client";
import { Banner, Button, Card, Field, Loading, PageHeader } from "../components/common";
import { IconFolder, IconPlay, IconPlus, IconUpload } from "../components/icons";
import { StartProgress } from "../components/StartProgress";
import { toast } from "../state/toast";

export function InvestigatePage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [caseIdentifier, setCaseIdentifier] = useState("");
  const [caseRole, setCaseRole] = useState("investigator");
  const [description, setDescription] = useState("");
  const [createdCaseId, setCreatedCaseId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [indType, setIndType] = useState("domain");
  const [indValue, setIndValue] = useState("");
  const [uploadedName, setUploadedName] = useState<string | null>(null);
  // Animated launch overlay: opens on click, completes on API success.
  const [launching, setLaunching] = useState(false);
  const launchedRunId = useRef<string | null>(null);

  const startMut = useMutation({
    mutationFn: (caseId: string) => startInvestigation(caseId),
    onSuccess: (investigation) => {
      launchedRunId.current = investigation.id;
      toast.success("Investigation started", "Agents are running in the background.");
    },
    onError: (err) => {
      const message = toApiError(err).message;
      setError(message);
      toast.error("Could not start investigation", message);
    },
  });

  /** Runs when the launch animation hits 100% — only ever after a real success. */
  const onLaunchComplete = () => {
    setLaunching(false);
    const runId = launchedRunId.current;
    launchedRunId.current = null;
    if (runId) navigate(`/app/investigations/${runId}`);
  };

  const createMut = useMutation({
    mutationFn: () => createCase(caseIdentifier, title, description, caseRole),
    onSuccess: (created) => {
      setCreatedCaseId(created.id);
      setError(null);
      void qc.invalidateQueries({ queryKey: ["cases"] });
      toast.success("Case created", created.title);
    },
    onError: (err) => {
      const message = toApiError(err).message;
      setError(message);
      toast.error("Could not create case", message);
    },
  });

  const indicatorMut = useMutation({
    mutationFn: () => submitIndicator(createdCaseId ?? "", indType, indValue),
    onSuccess: () => {
      const added = indValue.trim();
      setIndValue("");
      setError(null);
      void qc.invalidateQueries({ queryKey: ["evidence", createdCaseId] });
      toast.success("Indicator added", added);
    },
    onError: (err) => {
      const message = toApiError(err).message;
      setError(message);
      toast.error("Indicator rejected", message);
    },
  });

  const uploadMut = useMutation({
    mutationFn: (file: File) => uploadFile(createdCaseId ?? "", file),
    onSuccess: (_evidence, file) => {
      setUploadedName(file.name);
      setError(null);
      void qc.invalidateQueries({ queryKey: ["evidence", createdCaseId] });
      toast.success("Evidence uploaded", file.name);
    },
    onError: (err) => {
      const message = toApiError(err).message;
      setError(message);
      toast.error("Upload failed", message);
    },
  });

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (title.trim()) createMut.mutate();
  };

  const onIndicator = (event: FormEvent) => {
    event.preventDefault();
    if (createdCaseId && indValue.trim()) indicatorMut.mutate();
  };

  const onFile = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file && createdCaseId) uploadMut.mutate(file);
    event.target.value = "";
  };

  const reset = () => {
    setTitle("");
    setCaseIdentifier("");
    setCaseRole("investigator");
    setDescription("");
    setCreatedCaseId(null);
    setError(null);
  };

  return (
    <>
      <PageHeader
        title="Investigate"
        //subtitle="Create a case and start a human-supervised investigation."
      />

      <Card title="Create a case" tone="violet" icon={<IconFolder size={16} />}>
        <form onSubmit={onSubmit}>
            <Field label="Case ID" htmlFor="case-identifier">
              <input
                id="case-identifier"
                className="tg-input"
                value={caseIdentifier}
                onChange={(event) => setCaseIdentifier(event.target.value)}
                placeholder="e.g. CASE-2026-001"
                required
                disabled={createdCaseId !== null}
              />
            </Field>
            <Field label="Title" htmlFor="title">
              <input
                id="title"
                className="tg-input"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="e.g. Phishing cluster — Acme accounts"
                required
                disabled={createdCaseId !== null}
              />
            </Field>
            <Field
              label="Description"
              htmlFor="description"
              //hint="Optional context shown to case members."
            >
              <textarea
                id="description"
                className="tg-textarea"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="What are we trying to establish?"
                disabled={createdCaseId !== null}
              />
            </Field>
            <Field label="Your case role" htmlFor="case-role">
              <select
                id="case-role"
                className="tg-select"
                value={caseRole}
                onChange={(event) => setCaseRole(event.target.value)}
                disabled={createdCaseId !== null}
              >
                <option value="lead">Lead</option>
                <option value="investigator">Investigator</option>
                <option value="reviewer">Reviewer</option>
                <option value="viewer">Viewer</option>
              </select>
            </Field>
            {error && <Banner tone="error">{error}</Banner>}
            {createdCaseId ? (
              <p className="tg-hint">Case created. Add evidence below before starting the investigation.</p>
            ) : (
              <Button
                type="submit"
                variant="primary"
                fullWidth
                disabled={createMut.isPending || !caseIdentifier.trim() || !title.trim()}
                icon={<IconPlus size={16} />}
              >
                {createMut.isPending ? "Creating…" : "Create case"}
              </Button>
            )}
        </form>
        {createdCaseId && (
          <>
            <hr className="tg-divider" />
            <h3 className="tg-card-title">
              <span className="tg-card-title-icon">
                <IconPlus size={16} />
              </span>
              Add evidence
            </h3>
            <form onSubmit={onIndicator}>
              <div className="tg-input-row">
                <Field label="Indicator type" htmlFor="investigate-indtype">
                  <select
                    id="investigate-indtype"
                    className="tg-select"
                    value={indType}
                    onChange={(event) => setIndType(event.target.value)}
                    style={{ width: "auto", minWidth: 150 }}
                  >
                    {["username", "email", "domain", "ip", "wallet", "tx_hash"].map((type) => (
                      <option key={type} value={type}>
                        {type}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Value" htmlFor="investigate-indval">
                  <input
                    id="investigate-indval"
                    className="tg-input"
                    value={indValue}
                    onChange={(event) => setIndValue(event.target.value)}
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

            <label
              id="investigate-dropzone"
              className="tg-dropzone"
              htmlFor="investigate-file-input"
              tabIndex={0}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  document.getElementById("investigate-file-input")?.click();
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
              <input id="investigate-file-input" type="file" onChange={onFile} />
            </label>
            <p className="tg-hint">
              Text, PDF and Office (docx/xlsx/pptx) files are scanned for usernames, emails, IPs
              and domains when an investigation runs.
            </p>
            {uploadMut.isPending && <Loading label="Uploading file…" />}
            {uploadedName && uploadMut.isSuccess && (
              <Banner tone="success">
                Uploaded <strong>{uploadedName}</strong> — it will be included in the next
                investigation.
              </Banner>
            )}
            {error && <Banner tone="error">{error}</Banner>}
            <div className="tg-stack-sm tg-mt-4">
              <Button
                type="button"
                variant="primary"
                fullWidth
                onClick={() => {
                  if (!createdCaseId || startMut.isPending) return;
                  launchedRunId.current = null;
                  startMut.reset();
                  setLaunching(true);
                  startMut.mutate(createdCaseId);
                }}
                disabled={startMut.isPending}
                icon={<IconPlay size={16} />}
              >
                {startMut.isPending ? "Starting…" : "Start investigation"}
              </Button>
              <Button type="button" variant="ghost" fullWidth onClick={reset}>
                Create another case
              </Button>
            </div>
          </>
        )}
      </Card>

      <StartProgress
        open={launching}
        ready={startMut.isSuccess}
        title="Starting investigation"
        readyDetail="Run created — opening the live view…"
        error={startMut.isError ? toApiError(startMut.error).message : null}
        onComplete={onLaunchComplete}
        onClose={() => {
          setLaunching(false);
          startMut.reset();
        }}
      />
    </>
  );
}

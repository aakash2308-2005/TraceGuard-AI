import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { closeCase, listCases } from "../api/endpoints";
import { toApiError } from "../api/client";
import { toast } from "../state/toast";
import {
  Button,
  Card,
  DataTable,
  EmptyState,
  ErrorBanner,
  Loading,
  PageHeader,
  StatusPill,
} from "../components/common";
import { IconFolder, IconSearch } from "../components/icons";
import { SortMenu } from "../components/SortMenu";
import { DEFAULT_CASE_SORT, sortCases } from "../utils/caseSort";
import type { CaseSort } from "../utils/caseSort";
import { formatDate, formatRelative, titleCase } from "../utils/format";

export function CaseListPage() {
  const qc = useQueryClient();
  const { data, isLoading, isError } = useQuery({ queryKey: ["cases"], queryFn: listCases });
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<CaseSort>(DEFAULT_CASE_SORT);
  const closeMut = useMutation({
    mutationFn: closeCase,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["cases"] });
      toast.success("Case closed", "The case has been marked as closed.");
    },
    onError: (err) => toast.error("Closing case failed", toApiError(err).message),
  });

  const handleClose = (caseId: string) => {
    if (window.confirm("Are you sure you want to close this case?")) {
      closeMut.mutate(caseId);
    }
  };

  const filtered = useMemo(() => {
    const items = data ?? [];
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (c) =>
        c.case_identifier.toLowerCase().includes(q) ||
        c.title.toLowerCase().includes(q) ||
        (c.description ?? "").toLowerCase().includes(q) ||
        c.status.toLowerCase().includes(q),
    );
  }, [data, query]);

  const sorted = useMemo(() => sortCases(filtered, sort), [filtered, sort]);

  const columns = ["Case ID", "Case", "Status", "Role", "Created", "Actions"];
  const rows = sorted.map((c) => [
    <span key={`${c.id}-identifier`} className="tg-list-title">
      {c.case_identifier}
    </span>,
    <div key={c.id}>
      <Link to={`/app/cases/${c.id}`} className="tg-list-title">
        {c.title}
      </Link>
      {c.description && <div className="tg-list-meta tg-truncate">{c.description}</div>}
    </div>,
    <StatusPill key={`${c.id}-s`} value={c.status} />,
    c.my_case_role ? titleCase(c.my_case_role) : "—",
    <span key={`${c.id}-d`}>
      <div>{formatDate(c.created_at)}</div>
      <div className="tg-list-meta">{formatRelative(c.created_at)}</div>
    </span>,
    <div key={`${c.id}-a`} className="tg-row tg-wrap">
      <Link className="tg-button tg-button-sm" to={`/app/cases/${c.id}`}>
        Open
      </Link>
      {c.status !== "closed" && (
        <Button
          variant="danger"
          size="sm"
          onClick={() => handleClose(c.id)}
          disabled={closeMut.isPending}
        >
          Close
        </Button>
      )}
    </div>,
  ]);

  return (
    <>
      <PageHeader
        title="Cases"
        //subtitle="Every investigation lives inside a case, with its own evidence, members, and audit trail."
        actions={
          <span className="tg-pill tg-pill-info">{data ? `${data.length} total` : "…"}</span>
        }
      />

      <Card
            title="All cases"
            tone="blue"
            icon={<IconFolder size={16} />}
            actions={
              <div style={{ display: "flex", alignItems: "center", gap: "var(--tg-space-3)" }}>
                <SortMenu value={sort} onChange={setSort} align="right" />
                <div className="tg-input-group" style={{ minWidth: 220 }}>
                  <input
                    className="tg-input"
                    placeholder="Search cases…"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    aria-label="Search cases"
                    style={{ marginBottom: 0, paddingLeft: 34 }}
                  />
                  <span
                    className="tg-input-affix"
                    aria-hidden="true"
                    style={{ right: "auto", left: 9, pointerEvents: "none" }}
                  >
                    <IconSearch size={15} />
                  </span>
                </div>
              </div>
            }
            bodyClassName="tg-flush"
          >
            {isLoading && (
              <div style={{ padding: "var(--tg-space-6)" }}>
                <Loading label="Loading cases…" />
              </div>
            )}
            {isError && (
              <div style={{ padding: "var(--tg-space-6)" }}>
                <ErrorBanner message="Could not load cases." />
              </div>
            )}
            {data && data.length === 0 && (
              <EmptyState
                title="No cases yet"
                message="A case is the container for everything an investigation produces — evidence, indicators, agent runs and the audit trail."
              />
            )}
            {data && data.length > 0 && filtered.length === 0 && (
              <EmptyState
                title="No matches"
                message={`Nothing matched “${query}”. Try a different search term.`}
                action={
                  <Button variant="ghost" onClick={() => setQuery("")}>
                    Clear search
                  </Button>
                }
              />
            )}
            {filtered.length > 0 && <DataTable columns={columns} rows={rows} />}
          </Card>
    </>
  );
}

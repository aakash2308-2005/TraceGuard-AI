import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { getCaseAudit } from "../api/endpoints";
import {
  Card,
  DataTable,
  EmptyState,
  ErrorBanner,
  Loading,
  Note,
  PageHeader,
} from "../components/common";
import { IconArrowLeft, IconScroll } from "../components/icons";
import { formatDateTime, shortHash } from "../utils/format";

export function AuditPage() {
  const { caseId = "" } = useParams();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["audit", caseId],
    queryFn: () => getCaseAudit(caseId),
  });

  return (
    <>
      <Link to={`/app/cases/${caseId}`} className="tg-back-link">
        <IconArrowLeft size={15} /> Back to case
      </Link>

      <PageHeader
        title="Audit history"
        //subtitle="Every action recorded against this case."
        actions={
          <span className="tg-pill tg-pill-info">
            {data ? `${data.length} entr${data.length === 1 ? "y" : "ies"}` : "…"}
          </span>
        }
      />

      <Card
        title="Append-only audit log"
        tone="cyan"
        icon={<IconScroll size={16} />}
        //subtitle="Entries are hash-chained: each entry hash depends on the previous one, so tampering is detectable."
      >
        {isLoading && <Loading label="Loading audit history…" />}
        {isError && <ErrorBanner message="Could not load audit (requires audit visibility)." />}

        {data && data.length === 0 && (
          <EmptyState
            icon={<IconScroll size={22} />}
            title="No audit events yet"
            message="Actions performed on this case will be recorded here."
          />
        )}

        {data && data.length > 0 && (
          <>
            <DataTable
              columns={["When", "Action", "Actor", "Entry hash"]}
              rows={data.map((e) => [
                <span key={`${e.id}-w`}>
                  <div>{formatDateTime(e.created_at)}</div>
                </span>,
                <span key={`${e.id}-a`} className="tg-break">
                  {e.action.replace(/_/g, " ")}
                </span>,
                <span key={`${e.id}-r`} className="tg-dim">
                  {e.actor_id ? e.actor_id.slice(0, 8) : "system"}
                </span>,
                <span key={`${e.id}-h`} className="tg-hash" title={e.entry_hash}>
                  {shortHash(e.entry_hash)}
                </span>,
              ])}
            />
            <div style={{ padding: "var(--tg-space-4) var(--tg-space-6) 0" }}>
              <Note icon={<IconScroll size={16} />}>
                Because each entry commits to the previous hash, editing or deleting an entry breaks
                the chain and is immediately detectable.
              </Note>
            </div>
          </>
        )}
      </Card>
    </>
  );
}

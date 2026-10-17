import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { getCaseTimeline } from "../api/endpoints";
import {
  Card,
  EmptyState,
  ErrorBanner,
  Loading,
  PageHeader,
  Pill,
} from "../components/common";
import { IconArrowLeft, IconClock, IconInfo } from "../components/icons";

export function CaseTimelinePage() {
  const { caseId = "" } = useParams();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["case-timeline", caseId],
    queryFn: () => getCaseTimeline(caseId),
  });

  return (
    <>
      <Link to={`/app/cases/${caseId}`} className="tg-back-link">
        <IconArrowLeft size={15} /> Back to case
      </Link>

      <PageHeader
        title="Case timeline"
        subtitle="Every meaningful event for this case, ordered in time."
        actions={
          <span className="tg-pill tg-pill-info">
            {data ? `${data.length} event${data.length === 1 ? "" : "s"}` : "…"}
          </span>
        }
      />

      <Card title="Chronological events" tone="blue" icon={<IconClock size={16} />}>
        {isLoading && <Loading label="Loading timeline…" />}
        {isError && <ErrorBanner message="Could not load the case timeline." />}

        {data && data.length === 0 && (
          <EmptyState
            icon={<IconClock size={22} />}
            title="No timeline events yet"
            message="Events appear as evidence is added and investigations run."
          />
        )}

        {data && data.length > 0 && (
          <ol className="tg-timeline">
            {data.map((ev, i) => (
              <li key={i} className="tg-timeline-item">
                <span className="tg-timeline-dot" aria-hidden="true" />
                <div className="tg-timeline-time">{ev.at}</div>
                <div className="tg-timeline-label tg-break">
                  {ev.label ?? "event"}{" "}
                  {ev.source && <Pill tone="neutral">{ev.source}</Pill>}
                </div>
              </li>
            ))}
          </ol>
        )}

        <p className="tg-hint">
          <IconInfo size={14} /> The timeline is derived from evidence and investigation activity,
          not from a self-reported narrative.
        </p>
      </Card>
    </>
  );
}

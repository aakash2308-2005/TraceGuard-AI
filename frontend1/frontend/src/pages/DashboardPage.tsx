import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { listCases } from "../api/endpoints";
import { Card, EmptyState, ErrorBanner, Loading, PageHeader, Pill, Stat } from "../components/common";
import { useAuth } from "../state/auth";
import { formatDate, formatRelative, titleCase } from "../utils/format";
import {
  IconActivity,
  IconClock,
  IconFolder,
  IconPlus,
  IconLayers,
} from "../components/icons";

export function DashboardPage() {
  const { data, isLoading, isError } = useQuery({ queryKey: ["cases"], queryFn: listCases });
  const user = useAuth((s) => s.user);

  const cases = data ?? [];
  const active = cases.filter((c) => c.status === "active").length;
  const archived = cases.filter((c) => c.status === "archived" || c.status === "closed").length;
  const weekAgo = Date.now() - 7 * 86400_000;
  const recent = cases.filter((c) => new Date(c.created_at).getTime() >= weekAgo).length;
  const recentCases = [...cases]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 8);

  // Week-over-week change for "created this week". Growth reads green, a dip
  // amber (a warning, not a critical incident — red is reserved for critical).
  const prevWeek = cases.filter((c) => {
    const t = new Date(c.created_at).getTime();
    return t >= weekAgo - 7 * 86400_000 && t < weekAgo;
  }).length;
  const deltaPct = prevWeek > 0 ? Math.round(((recent - prevWeek) / prevWeek) * 100) : null;
  const deltaNode =
    deltaPct === null ? null : (
      <span className={deltaPct > 0 ? "tg-stat-delta-up" : deltaPct < 0 ? "tg-stat-delta-down" : undefined}>
        {deltaPct > 0 ? "↑" : deltaPct < 0 ? "↓" : "→"} {Math.abs(deltaPct)}% vs previous week
      </span>
    );

  return (
    <>
      <PageHeader
        title={`Welcome back, ${user?.username ?? "there"}`}
        //subtitle="Monitor active investigations, jump into a case, or start a new inquiry."
        actions={
          <Link className="tg-button tg-button-primary" to="/app/investigate">
            <IconPlus size={16} /> New case
          </Link>
        }
      />

      {isLoading && (
        <Card tone="blue">
          <Loading label="Loading dashboard…" />
        </Card>
      )}
      {isError && <ErrorBanner message="Could not load cases." />}

      {data && (
        <>
          <div className="tg-grid tg-grid-4" style={{ marginBottom: "var(--tg-space-5)" }}>
            <Stat
              variant="panel"
              label="Total cases"
              tone="violet"
              value={cases.length}
              icon={<IconFolder size={18} />}
              hint="Across all investigations"
            />
            <Stat
              variant="panel"
              label="Active"
              tone="blue"
              value={active}
              icon={<IconActivity size={18} />}
              hint="Open inquiries"
            />
            <Stat
              variant="panel"
              label="Created this week"
              tone="cyan"
              value={recent}
              icon={<IconClock size={18} />}
              delta={deltaNode}
              hint="Last 7 days"
            />
            <Stat
              variant="panel"
              label="Archived / closed"
              tone="slate"
              value={archived}
              icon={<IconLayers size={18} />}
              hint="Resolved cases"
            />
          </div>

          <div className="tg-grid tg-grid-3">
            <div className="tg-span-2">
              <Card
                title="Recent cases"
                tone="cyan"
                icon={<IconFolder size={16} />}
                subtitle="Newest first"
                actions={
                  <Link className="tg-button tg-button-sm" to="/app/cases">
                    View all
                  </Link>
                }
                bodyClassName="tg-flush"
              >
                {recentCases.length === 0 ? (
                  <div style={{ padding: "var(--tg-space-4) var(--tg-space-6)" }}>
                    <EmptyState
                      title="No cases yet"
                      message="Create your first case to start collecting evidence."
                      action={
                        <Link className="tg-button tg-button-primary tg-mt-2" to="/app/cases">
                          <IconPlus size={16} /> Create case
                        </Link>
                      }
                    />
                  </div>
                ) : (
                  <ul className="tg-list" style={{ padding: "0 var(--tg-space-6)" }}>
                    {recentCases.map((c) => (
                      <li key={c.id} className="tg-list-item">
                        <Link
                          to={`/app/cases/${c.id}`}
                          className="tg-list-row"
                          style={{ color: "inherit", textDecoration: "none" }}
                        >
                          <div className="tg-grow">
                            <div className="tg-list-title tg-truncate">{c.title}</div>
                            <div className="tg-list-meta">
                              Created {formatDate(c.created_at)} · {formatRelative(c.created_at)}
                            </div>
                          </div>
                          <div className="tg-row tg-wrap">
                            {c.my_case_role && <Pill tone="info">{titleCase(c.my_case_role)}</Pill>}
                            <Pill tone={c.status === "active" ? "success" : "neutral"}>
                              {titleCase(c.status)}
                            </Pill>
                          </div>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>

            <div>
              <Card title="Quick actions" tone="slate" icon={<IconActivity size={16} />}>
                <div className="tg-stack-sm">
                  <Link className="tg-button tg-button-primary tg-button-full" to="/app/investigate">
                    <IconPlus size={16} /> Create a new case
                  </Link>
                  <Link className="tg-button tg-button-full" to="/app/audit-help">
                    <IconFolder size={16} /> Help
                  </Link>
                  <Link className="tg-button tg-button-full" to="/app/cases">
                    <IconLayers size={16} /> Browse all cases
                  </Link>
                </div>
                <hr className="tg-divider" />
                
              </Card>

            </div>
          </div>

        </>
      )}
    </>
  );
}

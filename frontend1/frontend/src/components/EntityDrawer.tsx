import { useEffect, useRef, type ComponentType } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { getGraph } from "../api/endpoints";
import { useUi } from "../state/ui";
import { statusTone } from "../utils/status";
import { CopyButton } from "./CopyButton";
import { Button, Pill } from "./common";
import {
  IconActivity,
  IconFile,
  IconGlobe,
  IconGraph,
  IconHash,
  IconMail,
  IconUser,
  IconWallet,
  IconX,
  type IconProps,
} from "./icons";

const KIND_ICON: Record<string, ComponentType<IconProps>> = {
  Username: IconUser,
  Email: IconMail,
  Domain: IconGlobe,
  Url: IconGlobe,
  IpAddress: IconHash,
  Wallet: IconWallet,
  Transaction: IconActivity,
  File: IconFile,
};

function kindIcon(kind?: string) {
  const found = kind ? KIND_ICON[kind] : undefined;
  const Icon = found ?? IconHash;
  return <Icon size={18} />;
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="tg-kv">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

export function EntityDrawer() {
  const entity = useUi((s) => s.entity);
  const close = useUi((s) => s.closeEntity);
  const navigate = useNavigate();
  const panelRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (entity) {
      const id = requestAnimationFrame(() => panelRef.current?.focus());
      return () => cancelAnimationFrame(id);
    }
    return undefined;
  }, [entity]);

  // When we know which case we're in, use the existing graph endpoint to say
  // how deeply this value is entangled — no new backend surface required.
  const caseId = entity?.caseId ?? null;
  const { data: graph } = useQuery({
    queryKey: ["graph", caseId],
    queryFn: async () => {
      if (!caseId) throw new Error("Entity has no case context");
      return getGraph(caseId);
    },
    enabled: Boolean(caseId),
    staleTime: 60_000,
  });

  if (!entity) return null;

  const edges = entity.caseId
    ? (graph?.edges ?? []).filter((e) => e.source === entity.value || e.target === entity.value)
    : [];
  const related = edges
    .map((e) => (e.source === entity.value ? e.target : e.source))
    .slice(0, 6);

  return (
    <>
      <div className="tg-drawer-scrim" role="presentation" onMouseDown={close} />
      <aside
        ref={panelRef}
        className="tg-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={`Details for ${entity.value}`}
        tabIndex={-1}
      >
        <header className="tg-drawer-head">
          <span className="tg-drawer-kind" aria-hidden="true">
            {kindIcon(entity.kind)}
          </span>
          <div className="tg-grow">
            <div className="tg-drawer-kindname">{entity.kind ?? "Indicator"}</div>
            <div className="tg-drawer-sub">Entity detail</div>
          </div>
          <button type="button" className="tg-icon-btn" aria-label="Close entity detail" onClick={close}>
            <IconX size={16} />
          </button>
        </header>

        <div className="tg-drawer-body">
          <div className="tg-drawer-value">
            <code>{entity.value}</code>
            <CopyButton value={entity.value} label="Copy full value" />
          </div>

          <dl className="tg-kv-list">
            {entity.kind && (
              <Row label="Type">
                <span className="tg-drawer-type">{entity.kind}</span>
              </Row>
            )}
            {entity.status && (
              <Row label="Epistemic status">
                <Pill tone={statusTone(entity.status)}>{String(entity.status).replace(/_/g, " ")}</Pill>
              </Row>
            )}
            {entity.note && <Row label="Note">{entity.note}</Row>}
            <Row label="Length">
              {entity.value.length} characters
            </Row>
            {entity.caseId && graph && (
              <Row label="Relationships">
                {edges.length === 0 ? (
                  <span className="tg-dim">No edges recorded yet</span>
                ) : (
                  <>
                    {edges.length} edge{edges.length === 1 ? "" : "s"} · {related.length} distinct entit
                    {related.length === 1 ? "y" : "ies"}
                  </>
                )}
              </Row>
            )}
          </dl>

          {related.length > 0 && (
            <section className="tg-drawer-section">
              <h3>Co-occurring entities</h3>
              <ul className="tg-rel-list">
                {related.map((r) => (
                  <li key={r}>
                    <button
                      type="button"
                      className="tg-rel-chip"
                      title={r}
                      onClick={() => {
                        close();
                        // Re-open for the neighbour so drilling is one click.
                        useUi.getState().openEntity({ ...entity, value: r });
                      }}
                    >
                      {r}
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <p className="tg-note tg-drawer-note">
            Presence here means this value was <strong>observed in evidence</strong>. It is not proof
            that any person owns or controls it.
          </p>
        </div>

        <footer className="tg-drawer-foot">
          {entity.caseId && (
            <Button
              variant="primary"
              icon={<IconGraph size={16} />}
              onClick={() => {
                close();
                navigate(`/app/cases/${entity.caseId}/graph`);
              }}
            >
              Open in graph
            </Button>
          )}
          <CopyButton value={entity.value} label="Copy value" />
        </footer>
      </aside>
    </>
  );
}

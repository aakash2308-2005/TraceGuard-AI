import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import cytoscape from "cytoscape";
import { getCase, getGraph } from "../api/endpoints";
import { useUi } from "../state/ui";
import type { ExportableIndicator } from "../utils/export";
import { CopyButton } from "../components/CopyButton";
import { ExportMenu } from "../components/ExportMenu";
import {
  Button,
  Card,
  EmptyState,
  ErrorBanner,
  Loading,
  Note,
  PageHeader,
  Stat,
} from "../components/common";
import {
  IconArrowLeft,
  IconGraph,
  IconLayers,
  IconMaximize,
  IconMinus,
  IconPlus,
  IconTarget,
} from "../components/icons";

// Node colors by label. Color is reinforcement; the node label text is primary.
// Chart palette: muted purple = primary series, soft cyan = secondary series,
// deep navy = structural, slate = neutral. Red/orange/amber/green stay
// reserved for real status or severity, so entity types never use them.
// Light mode uses darker steps of the same hues: the dark palette sits at
// ~1.8:1 against white, under the 3:1 minimum for meaningful graphics.
const NODE_COLORS_DARK: Record<string, string> = {
  Username: "#22d3ee",
  Email: "#3b82f6",
  Domain: "#a855f7",
  IpAddress: "#f59e0b",
  Wallet: "#34d399",
  Transaction: "#f87171",
  File: "#94a3b8",
};

const NODE_COLORS_LIGHT: Record<string, string> = {
  Username: "#7566e8",
  Email: "#0891b2",
  Domain: "#142d4e",
  IpAddress: "#64748b",
  Wallet: "#5b4fd6",
  Transaction: "#0e7490",
  File: "#475569",
};

// Deterministic layouts read far more cleanly than a force-directed one, which
// reshuffles on every load. "concentric" puts the most-connected hub in the
// centre and rings outward by degree.
//
// spacingFactor on each layout is tuned so fit-zoom lands at ~1.0, keeping
// labels at their designed 10px. Every value below was measured for zero
// label-box collisions; a "breadthfirst" option was tried and dropped because
// it lays nodes in a wide row that only fits at ~0.75 zoom (7.5px labels).
type LayoutName = "concentric" | "circle" | "grid" | "force";

const LAYOUTS: Record<LayoutName, cytoscape.LayoutOptions> = {
  concentric: {
    name: "concentric",
    animate: false,
    fit: true,
    padding: 48,
    // Labels sit below each node and are far wider than the circle itself, so
    // the layout must space nodes by label dimensions — not just by shape.
    avoidOverlap: true,
    nodeDimensionsIncludeLabels: true,
    spacingFactor: 1.05,
    concentric: (node: cytoscape.NodeSingular) => node.degree(),
    levelWidth: () => 1,
  },
  circle: {
    name: "circle",
    animate: false,
    fit: true,
    padding: 48,
    avoidOverlap: true,
    nodeDimensionsIncludeLabels: true,
    spacingFactor: 0.95,
  },
  grid: {
    name: "grid",
    animate: false,
    fit: true,
    padding: 48,
    avoidOverlap: true,
    nodeDimensionsIncludeLabels: true,
    condense: false,
    spacingFactor: 1.1,
  },
  force: {
    name: "cose",
    animate: false,
    fit: true,
    padding: 48,
    nodeRepulsion: () => 20000,
    idealEdgeLength: () => 200,
    nodeOverlap: 40,
    nodeDimensionsIncludeLabels: true,
    gravity: 0.5,
    numIter: 1200,
  },
};

const LAYOUT_LABELS: Record<LayoutName, string> = {
  concentric: "Concentric",
  circle: "Circle",
  grid: "Grid",
  force: "Force",
};

// Cytoscape cannot word-wrap long unbroken strings (addresses, hashes, file
// IDs), so full-length values blow out across the canvas and collide. Show a
// short head…tail abbreviation on the node; the full value is revealed in the
// details panel and in the underlying data.
function abbreviate(value: string): string {
  const v = value ?? "";
  if (v.length <= 18) return v;
  return `${v.slice(0, 8)}…${v.slice(-4)}`;
}

export function GraphPage() {
  const { caseId = "" } = useParams();
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const layoutRef = useRef<LayoutName>("concentric");

  const [layout, setLayout] = useState<LayoutName>("concentric");
  const [selected, setSelected] = useState<string | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["graph", caseId],
    queryFn: () => getGraph(caseId),
  });

  // Theme drives both the node palette and the label/edge colours below, so
  // the instance is rebuilt when it flips.
  const theme = useUi((s) => s.theme);
  const nodeColors = theme === "light" ? NODE_COLORS_LIGHT : NODE_COLORS_DARK;
  // Stable per theme so the cytoscape effect can depend on it safely.
  const colorOf = useCallback(
    (kind: string) => nodeColors[kind] ?? nodeColors.File,
    [nodeColors],
  );
  const openEntity = useUi((s) => s.openEntity);

  // Case title feeds export filenames; shares CaseDetailPage's cache key.
  const { data: caseInfo } = useQuery({
    queryKey: ["case", caseId],
    queryFn: () => getCase(caseId),
    staleTime: 60_000,
  });

  const exportable: ExportableIndicator[] = (data?.nodes ?? []).map((n) => ({
    value: n.value,
    type: n.label.toLowerCase(),
  }));

  const kinds = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const n of data?.nodes ?? []) counts[n.label] = (counts[n.label] ?? 0) + 1;
    return Object.entries(counts).sort((a, b) => b[1] - a[1]);
  }, [data]);

  // Create the cytoscape instance once per dataset (or per theme).
  useEffect(() => {
    if (!data || !containerRef.current) return;

    // Pull text/edge colours from the live tokens so the canvas follows the
    // same theme as the DOM rather than hardcoding a second palette.
    const computed = getComputedStyle(document.documentElement);
    const read = (name: string, fallback: string) => computed.getPropertyValue(name).trim() || fallback;
    const labelColor = read("--tg-text", "#e9eefb");
    const haloColor = read("--tg-bg", "#0a1120");
    const edgeColor = read("--tg-border-strong", "#2b3c5e");
    const edgeLabelColor = read("--tg-text-muted", "#c7d2e5");
    const accentColor = read("--tg-accent", "#22d3ee");

    const elements: cytoscape.ElementDefinition[] = [
      ...data.nodes.map((n) => ({
        data: { id: n.id, label: `${n.label}\n${abbreviate(n.value)}`, kind: n.label },
      })),
      ...data.edges.map((e, i) => ({
        data: { id: `e${i}`, source: e.source, target: e.target, label: e.rel },
      })),
    ];

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: "node",
          style: {
            "background-color": (ele: cytoscape.NodeSingular) =>
              colorOf(ele.data("kind")),
            label: "data(label)",
            color: labelColor,
            "font-size": "10px",
            "font-weight": 600,
            "font-family": "Inter, system-ui, sans-serif",
            "text-wrap": "wrap",
            "text-max-width": "92px",
            "text-valign": "bottom",
            "text-margin-y": 6,
            "text-outline-color": haloColor,
            "text-outline-width": 3,
            width: 30,
            height: 30,
            "border-width": 2,
            "border-color": haloColor,
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.5,
            "line-color": edgeColor,
            "target-arrow-color": edgeColor,
            "target-arrow-shape": "triangle",
            "arrow-scale": 1.1,
            "curve-style": "bezier",
            // Keep edges quiet by default; reveal the relation on hover.
            label: "",
            "font-size": "9px",
            "font-family": "Inter, system-ui, sans-serif",
            color: edgeLabelColor,
            "text-rotation": "autorotate",
            "text-background-color": haloColor,
            "text-background-opacity": 0.9,
            "text-background-padding": "3px",
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-width": 4,
            "border-color": accentColor,
          },
        },
        {
          // Hover: bring the focused node and its neighbours forward, dim the rest.
          selector: ".dim",
          style: { opacity: 0.15 },
        },
        {
          // Beyond a certain zoom-out, labels collapse into an unreadable soup —
          // the mess this view used to be. Cull labels to bare dots when zoomed
          // out; hovering or selecting still reveals the label.
          selector: "node.nolabel",
          style: { label: "" },
        },
        {
          selector: "node.nolabel:hover, node.nolabel:selected",
          style: { label: "data(label)" },
        },
        {
          selector: "node:hover",
          style: { "border-width": 4, "border-color": accentColor },
        },
        {
          selector: "edge:hover",
          style: {
            "line-color": accentColor,
            "target-arrow-color": accentColor,
            width: 2.5,
            label: "data(label)",
          },
        },
      ],
      layout: LAYOUTS[layoutRef.current],
      wheelSensitivity: 0.2,
      minZoom: 0.2,
      maxZoom: 4,
    });

    cyRef.current = cy;

    const focus = (node: cytoscape.NodeSingular | null) => {
      cy.elements().removeClass("dim");
      if (node) node.closedNeighborhood().nodes().removeClass("dim");
      cy.elements()
        .difference(node ? node.closedNeighborhood() : cy.elements())
        .addClass("dim");
    };

    cy.on("mouseover", "node", (e) => focus(e.target as cytoscape.NodeSingular));
    cy.on("mouseout", "node", () => focus(null));
    cy.on("tap", "node", (e) => setSelected((e.target as cytoscape.NodeSingular).id()));
    cy.on("tap", (e) => {
      if (e.target === cy) setSelected(null);
    });

    // Cull labels once zoom drops far enough that they'd overlap into mush.
    // Guarded per-node so repeat zoom events on large graphs stay cheap.
    const syncLabelCulling = () => {
      const cull = cy.zoom() < 0.55;
      cy.batch(() => {
        cy.nodes().forEach((n) => {
          const has = n.hasClass("nolabel");
          if (cull && !has) n.addClass("nolabel");
          else if (!cull && has) n.removeClass("nolabel");
        });
      });
    };
    cy.on("zoom", syncLabelCulling);
    syncLabelCulling();

    return () => {
      cyRef.current = null;
      cy.destroy();
    };
  }, [data, theme, colorOf]);

  // Re-run the layout when the user switches layouts.
  useEffect(() => {
    layoutRef.current = layout;
    cyRef.current?.layout(LAYOUTS[layout]).run();
  }, [layout]);

  const zoomBy = useCallback((factor: number) => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.animate({ zoom: cy.zoom() * factor, duration: 150 }, {});
  }, []);

  const fitGraph = useCallback(() => {
    cyRef.current?.fit(undefined, 48);
  }, []);

  const selectedNode = useMemo(
    () => (selected ? (data?.nodes.find((n) => n.id === selected) ?? null) : null),
    [selected, data],
  );
  const selectedEdges = useMemo(
    () =>
      selected
        ? (data?.edges.filter((e) => e.source === selected || e.target === selected) ?? [])
        : [],
    [selected, data],
  );

  return (
    <>
      <Link to={`/app/cases/${caseId}`} className="tg-back-link">
        <IconArrowLeft size={15} /> Back to case
      </Link>

      <PageHeader
        title="Relationship graph"
        subtitle="Entities extracted from evidence and the edges between them."
        actions={
          <>
            <span className="tg-pill tg-pill-info">
              {data ? `${data.nodes.length} nodes · ${data.edges.length} edges` : "…"}
            </span>
            {data && data.nodes.length > 0 && (
              <ExportMenu caseTitle={caseInfo?.title ?? "case"} indicators={exportable} />
            )}
          </>
        }
      />

      {isLoading && (
        <Card tone="blue">
          <Loading label="Rendering graph…" />
        </Card>
      )}
      {isError && <ErrorBanner message="Could not load graph." />}

      {data && (
        <>
          {data.note && (
            <Card tone="cyan">
              <Note icon={<IconTarget size={16} />}>{data.note}</Note>
            </Card>
          )}

          <div className="tg-grid tg-grid-3" style={{ marginBottom: "var(--tg-space-5)" }}>
            <Stat label="Entities" tone="violet" value={data.nodes.length} icon={<IconTarget size={22} />} />
            <Stat label="Connections" tone="blue" value={data.edges.length} icon={<IconLayers size={22} />} />
            <Stat
              label="Node types"
              tone="cyan"
              value={kinds.length}
              icon={<IconGraph size={22} />}
              hint={kinds.map(([k]) => k).slice(0, 3).join(", ")}
            />
          </div>

          <Card
            title="Entity network"
            tone="slate"
            icon={<IconGraph size={16} />}
            subtitle="Edges record co-occurrence with provenance — a connection is not proof of identity."
          >
            {data.nodes.length === 0 && !data.note ? (
              <EmptyState
                icon={<IconGraph size={22} />}
                title="No graph yet"
                message="Run an investigation to populate the relationship graph."
              />
            ) : (
              <>
                <div className="tg-graph-shell">
                  {/* Floating controls */}
                  <div className="tg-graph-toolbar">
                    <div className="tg-graph-toolbar-group">
                      {(Object.keys(LAYOUT_LABELS) as LayoutName[]).map(
                        (name) => (
                          <button
                            key={name}
                            type="button"
                            className="tg-graph-layout-btn"
                            aria-pressed={layout === name}
                            onClick={() => setLayout(name)}
                          >
                            {LAYOUT_LABELS[name]}
                          </button>
                        ),
                      )}
                    </div>
                    <div className="tg-graph-toolbar-group">
                      <Button
                        size="sm"
                        ariaLabel="Zoom in"
                        title="Zoom in"
                        icon={<IconPlus size={15} />}
                        onClick={() => zoomBy(1.25)}
                      />
                      <Button
                        size="sm"
                        ariaLabel="Zoom out"
                        title="Zoom out"
                        icon={<IconMinus size={15} />}
                        onClick={() => zoomBy(0.8)}
                      />
                      <Button
                        size="sm"
                        ariaLabel="Fit to view"
                        title="Fit to view"
                        icon={<IconMaximize size={15} />}
                        onClick={fitGraph}
                      />
                    </div>
                  </div>

                  <div
                    ref={containerRef}
                    style={{ width: "100%", height: "100%" }}
                    role="img"
                    aria-label="Relationship graph of entities"
                  />
                </div>

                <div className="tg-legend">
                  {kinds.map(([kind, count]) => (
                    <span key={kind} className="tg-legend-item">
                      <span
                        className="tg-legend-swatch"
                        style={{ background: colorOf(kind) }}
                        aria-hidden="true"
                      />
                      {kind}
                      <span className="tg-dim">· {count}</span>
                    </span>
                  ))}
                </div>

                {selectedNode ? (
                  <div className="tg-graph-detail tg-mt-4">
                    <span
                      className="tg-graph-detail-swatch"
                      style={{ background: colorOf(selectedNode.label) }}
                      aria-hidden="true"
                    />
                    <div className="tg-grow" style={{ minWidth: 0 }}>
                      <div className="tg-list-title">{selectedNode.label}</div>
                      <code className="tg-break tg-hash">{selectedNode.value}</code>
                      {selectedEdges.length > 0 && (
                        <div className="tg-list-meta tg-mt-2">
                          Connected to:{" "}
                          {selectedEdges
                            .map((e) =>
                              e.source === selected
                                ? data.nodes.find((n) => n.id === e.target)?.value ?? e.target
                                : data.nodes.find((n) => n.id === e.source)?.value ?? e.source,
                            )
                            .join(", ")}
                        </div>
                      )}
                    </div>
                    <div className="tg-graph-detail-actions">
                      <Button
                        size="sm"
                        onClick={() =>
                          openEntity({
                            value: selectedNode.value,
                            kind: selectedNode.label,
                            caseId,
                          })
                        }
                      >
                        Details
                      </Button>
                      <CopyButton value={selectedNode.value} label="Copy value" iconOnly />
                    </div>
                  </div>
                ) : (
                  <p className="tg-hint tg-mt-4">
                    Hover a node to focus its connections; hover an edge to read its relation; click
                    a node for full details. Drag to pan, scroll to zoom.
                  </p>
                )}
              </>
            )}
          </Card>
        </>
      )}
    </>
  );
}

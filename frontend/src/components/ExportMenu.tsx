import { useEffect, useRef, useState } from "react";
import { toast } from "../state/toast";
import { downloadText, exportIndicators, type ExportableIndicator } from "../utils/export";
import { Button } from "./common";
import { IconDownload, IconFile, IconLayers, IconScroll } from "./icons";

const FORMATS = [
  { id: "csv" as const, label: "CSV", detail: "Spreadsheet / bulk review", icon: <IconFile size={15} /> },
  { id: "json" as const, label: "JSON", detail: "Structured, includes metadata", icon: <IconLayers size={15} /> },
  { id: "stix" as const, label: "STIX 2.1", detail: "Threat-intel interchange", icon: <IconScroll size={15} /> },
];

/**
 * Dropdown export of a case's indicators. Built on browser primitives so no
 * backend endpoint (or new permission surface) is required.
 */
export function ExportMenu({
  caseTitle,
  indicators,
  align = "right",
}: {
  caseTitle: string;
  indicators: ExportableIndicator[];
  align?: "left" | "right";
}) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const run = (format: "csv" | "json" | "stix") => {
    const file = exportIndicators(format, caseTitle, indicators);
    downloadText(file.filename, file.content, file.mime);
    setOpen(false);
    toast.success(`Exported ${indicators.length} indicator${indicators.length === 1 ? "" : "s"}`, file.filename);
  };

  return (
    <div className="tg-menu-wrap" ref={wrapRef}>
      <Button
        icon={<IconDownload size={16} />}
        onClick={() => setOpen((o) => !o)}
        ariaLabel="Export indicators"
        title="Export indicators"
        disabled={indicators.length === 0}
      >
        Export
      </Button>

      {open && (
        <div className={`tg-menu tg-menu-${align}`} role="menu" aria-label="Export format">
          <div className="tg-menu-head">Export {indicators.length} indicators</div>
          {FORMATS.map((f) => (
            <button key={f.id} type="button" role="menuitem" onClick={() => run(f.id)}>
              <span className="tg-menu-icon" aria-hidden="true">
                {f.icon}
              </span>
              <span>
                <span className="tg-menu-label">{f.label}</span>
                <span className="tg-menu-detail">{f.detail}</span>
              </span>
            </button>
          ))}
          {indicators.length === 0 && <div className="tg-menu-note">Nothing to export yet.</div>}
        </div>
      )}
    </div>
  );
}

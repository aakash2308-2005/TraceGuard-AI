import { useEffect, useRef, useState, type ReactNode } from "react";
import { SORT_LABELS, type CaseSort, type CaseSortKey } from "../utils/caseSort";
import {
  IconActivity,
  IconCheck,
  IconClock,
  IconFilter,
  IconFolder,
  IconHash,
  IconUsers,
} from "./icons";

interface SortOption {
  key: CaseSortKey;
  dir: "asc" | "desc";
  group: string;
  icon: ReactNode;
}

/** Ordered exactly as the menu should render, grouped by the `group` label. */
const OPTIONS: SortOption[] = [
  { key: "created", dir: "desc", group: "Date", icon: <IconClock size={15} /> },
  { key: "created", dir: "asc", group: "Date", icon: <IconClock size={15} /> },
  { key: "identifier", dir: "asc", group: "Case", icon: <IconHash size={15} /> },
  { key: "identifier", dir: "desc", group: "Case", icon: <IconHash size={15} /> },
  { key: "title", dir: "asc", group: "Case", icon: <IconFolder size={15} /> },
  { key: "title", dir: "desc", group: "Case", icon: <IconFolder size={15} /> },
  { key: "status", dir: "asc", group: "Case", icon: <IconActivity size={15} /> },
  { key: "role", dir: "asc", group: "Case", icon: <IconUsers size={15} /> },
];

/**
 * "Sort by" dropdown for list headers. Mirrors ExportMenu (outside-click and
 * Escape dismissal, menu/menuitemradio roles) so it behaves like the rest of
 * the app's popovers.
 */
export function SortMenu({
  value,
  onChange,
  align = "left",
}: {
  value: CaseSort;
  onChange: (sort: CaseSort) => void;
  align?: "left" | "right";
}) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        buttonRef.current?.focus();
      }
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const label = SORT_LABELS[value.key][value.dir];
  let lastGroup = "";

  return (
    <div className="tg-menu-wrap" ref={wrapRef}>
      <button
        type="button"
        className="tg-button"
        ref={buttonRef}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        title="Change sort order"
      >
        <IconFilter size={16} />
        Sort by: {label}
      </button>

      {open && (
        <div className={`tg-menu tg-menu-${align}`} role="menu" aria-label="Sort cases by">
          <div className="tg-menu-head">Sort cases by</div>
          {OPTIONS.map((opt) => {
            const head = opt.group !== lastGroup ? opt.group : null;
            lastGroup = opt.group;
            const active = opt.key === value.key && opt.dir === value.dir;
            return (
              <div key={`${opt.key}-${opt.dir}`}>
                {head && <div className="tg-menu-head">{head}</div>}
                <button
                  type="button"
                  role="menuitemradio"
                  aria-checked={active}
                  onClick={() => {
                    onChange({ key: opt.key, dir: opt.dir });
                    setOpen(false);
                    buttonRef.current?.focus();
                  }}
                >
                  <span className="tg-menu-icon" aria-hidden="true">
                    {opt.icon}
                  </span>
                  <span>
                    <span className="tg-menu-label">{SORT_LABELS[opt.key][opt.dir]}</span>
                  </span>
                  {active && (
                    <span className="tg-menu-check" aria-hidden="true">
                      <IconCheck size={15} />
                    </span>
                  )}
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

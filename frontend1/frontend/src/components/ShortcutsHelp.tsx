import { useEffect, useRef } from "react";
import { useUi } from "../state/ui";
import { SHORTCUTS } from "../utils/shortcuts";
import { IconKeyboard, IconX } from "./icons";

export function ShortcutsHelp() {
  const open = useUi((s) => s.shortcutsOpen);
  const close = useUi((s) => s.closeShortcuts);
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) {
      const id = requestAnimationFrame(() => dialogRef.current?.focus());
      return () => cancelAnimationFrame(id);
    }
    return undefined;
  }, [open]);

  if (!open) return null;

  const groups = Array.from(new Set(SHORTCUTS.map((s) => s.group)));

  return (
    <div className="tg-overlay" role="presentation" onMouseDown={close}>
      <div
        ref={dialogRef}
        className="tg-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Keyboard shortcuts"
        tabIndex={-1}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <header className="tg-modal-head">
          <span className="tg-modal-icon" aria-hidden="true">
            <IconKeyboard size={18} />
          </span>
          <div className="tg-grow">
            <h2 className="tg-modal-title">Keyboard shortcuts</h2>
            <div className="tg-modal-sub">Everything here works without leaving the keyboard.</div>
          </div>
          <button type="button" className="tg-icon-btn" aria-label="Close shortcuts" onClick={close}>
            <IconX size={16} />
          </button>
        </header>

        <div className="tg-modal-body">
          <div className="tg-shortcut-grid">
            {groups.map((group) => (
              <section key={group} className="tg-shortcut-group">
                <h3>{group}</h3>
                <ul>
                  {SHORTCUTS.filter((s) => s.group === group).map((s) => (
                    <li key={s.label}>
                      <span>{s.label}</span>
                      <span className="tg-shortcut-keys">
                        {s.keys.map((k, i) => (
                          <kbd className="tg-kbd" key={`${k}-${i}`}>
                            {k}
                          </kbd>
                        ))}
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

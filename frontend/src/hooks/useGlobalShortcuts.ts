import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useUi } from "../state/ui";
import { CHORD_TIMEOUT_MS } from "../utils/shortcuts";

/** True when the keystroke should be left alone (we're in a form field). */
function isTyping(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el || typeof el.tagName !== "string") return false;
  const tag = el.tagName.toLowerCase();
  return tag === "input" || tag === "textarea" || tag === "select" || el.isContentEditable === true;
}

/**
 * App-wide keyboard layer: ⌘K palette, "/" search, "?" help, "t" theme and
 * g-then-<key> navigation chords. Mounted once inside AppLayout so it only
 * exists for authenticated routes.
 */
export function useGlobalShortcuts() {
  const navigate = useNavigate();
  const chordRef = useRef<{ key: string; at: number } | null>(null);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      const key = e.key.toLowerCase();

      // The palette shortcut must win even while a field has focus — that's
      // the whole point of having it.
      if (mod && key === "k") {
        e.preventDefault();
        useUi.getState().togglePalette();
        return;
      }

      if (e.key === "Escape") {
        const s = useUi.getState();
        if (s.entity) s.closeEntity();
        else if (s.paletteOpen) s.closePalette();
        else if (s.shortcutsOpen) s.closeShortcuts();
        else if (s.settingsOpen) s.closeSettings();
        else (document.activeElement as HTMLElement | null)?.blur?.();
        return;
      }

      // While any overlay owns the screen, it owns the keyboard too.
      const ui = useUi.getState();
      if (ui.paletteOpen || ui.shortcutsOpen || ui.settingsOpen || ui.entity) return;

      if (isTyping(e.target) || mod || e.altKey) return;

      if (e.key === "/") {
        e.preventDefault();
        ui.openPalette();
        return;
      }
      if (e.key === "?") {
        e.preventDefault();
        ui.openShortcuts();
        return;
      }
      if (key === "t") {
        e.preventDefault();
        ui.toggleTheme();
        return;
      }

      const now = Date.now();
      const previous = chordRef.current;
      const inChord = Boolean(previous && previous.key === "g" && now - previous.at < CHORD_TIMEOUT_MS);
      chordRef.current = null;

      if (inChord) {
        const caseId = /\/app\/cases\/([^/?#]+)/.exec(window.location.pathname)?.[1];
        const targets: Record<string, string | null> = {
          d: "/app",
          c: "/app/cases",
          g: caseId ? `/app/cases/${caseId}/graph` : null,
          t: caseId ? `/app/cases/${caseId}/timeline` : null,
        };
        const to = targets[key];
        if (to) {
          e.preventDefault();
          navigate(to);
        }
        return;
      }

      if (key === "g") chordRef.current = { key: "g", at: now };
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [navigate]);
}

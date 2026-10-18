/**
 * Single source of truth for keyboard shortcuts — rendered by the help
 * overlay and implemented by useGlobalShortcuts, so the help text can never
 * drift away from the behaviour.
 *
 * Chords use lowercase key names (e.g. "g" then "d"); modifiers are listed
 * as separate entries so the UI can render them as <kbd> keys.
 */
export interface ShortcutDef {
  group: string;
  keys: string[];
  label: string;
}

export const SHORTCUTS: ShortcutDef[] = [
  { group: "Global", keys: ["Ctrl", "K"], label: "Open the command palette" },
  { group: "Global", keys: ["/"], label: "Search from anywhere" },
  { group: "Global", keys: ["?"], label: "Show this shortcut list" },
  { group: "Global", keys: ["Esc"], label: "Close an overlay or drawer" },
  { group: "Navigate", keys: ["g", "d"], label: "Go to dashboard" },
  { group: "Navigate", keys: ["g", "c"], label: "Go to cases" },
  { group: "Navigate", keys: ["g", "g"], label: "Go to this case's graph" },
  { group: "Navigate", keys: ["g", "t"], label: "Go to this case's timeline" },
  { group: "Appearance", keys: ["t"], label: "Toggle light / dark theme" },
  { group: "Palette", keys: ["↑", "↓"], label: "Move through results" },
  { group: "Palette", keys: ["↵"], label: "Run the highlighted command" },
];

export const CHORD_TIMEOUT_MS = 1200;

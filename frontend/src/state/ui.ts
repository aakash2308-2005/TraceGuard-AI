import { create } from "zustand";

/**
 * Global UI state: appearance (accent + light/dark) and the handful of
 * full-screen surfaces (command palette, shortcut help, settings, entity
 * drawer). Appearance is mirrored onto <html data-accent/data-theme> so the
 * CSS tokens do the actual work, and persisted so the choice survives reloads.
 */

export type Accent = "cyan" | "violet" | "emerald" | "amber";
export type ThemeMode = "dark" | "light";

/** Anything the right-hand drawer can present. `value` is always the full,
 *  unabbreviated indicator so the drawer never repeats the graph's truncation. */
export interface EntityRef {
  value: string;
  kind?: string;
  caseId?: string;
  /** Optional richer payload already known by the caller. */
  note?: string;
  status?: string;
}

export const ACCENTS: Accent[] = ["cyan", "violet", "emerald", "amber"];

export const ACCENT_LABEL: Record<Accent, string> = {
  cyan: "Cyan",
  violet: "Violet",
  emerald: "Emerald",
  amber: "Amber",
};

const readAccent = (): Accent => {
  const raw = localStorage.getItem("tg_accent");
  // Brand accent is muted purple by default (TraceGuard colour system).
  return (ACCENTS as string[]).includes(raw ?? "") ? (raw as Accent) : "violet";
};

const readTheme = (): ThemeMode => {
  const stored = localStorage.getItem("tg_theme");
  if (stored === "dark" || stored === "light") return stored;
  // No explicit choice yet — the interface is white-themed by default.
  return "light";
};

/** Mirror the persisted choice onto the document. Safe to call repeatedly. */
export function applyAppearance(accent: Accent, theme: ThemeMode) {
  const root = document.documentElement;
  root.dataset.accent = accent;
  root.dataset.theme = theme;
  root.style.colorScheme = theme;
}

interface UiState {
  accent: Accent;
  theme: ThemeMode;

  paletteOpen: boolean;
  shortcutsOpen: boolean;
  settingsOpen: boolean;
  entity: EntityRef | null;

  setAccent: (accent: Accent) => void;
  setTheme: (theme: ThemeMode) => void;
  toggleTheme: () => void;

  openPalette: () => void;
  closePalette: () => void;
  togglePalette: () => void;

  openShortcuts: () => void;
  closeShortcuts: () => void;

  toggleSettings: () => void;
  closeSettings: () => void;

  openEntity: (entity: EntityRef) => void;
  closeEntity: () => void;
}

const initialAccent = readAccent();
const initialTheme = readTheme();

export const useUi = create<UiState>((set, get) => ({
  accent: initialAccent,
  theme: initialTheme,

  paletteOpen: false,
  shortcutsOpen: false,
  settingsOpen: false,
  entity: null,

  setAccent: (accent) => {
    localStorage.setItem("tg_accent", accent);
    applyAppearance(accent, get().theme);
    set({ accent });
  },

  setTheme: (theme) => {
    localStorage.setItem("tg_theme", theme);
    applyAppearance(get().accent, theme);
    set({ theme });
  },

  toggleTheme: () => get().setTheme(get().theme === "dark" ? "light" : "dark"),

  openPalette: () => set({ paletteOpen: true }),
  closePalette: () => set({ paletteOpen: false }),
  togglePalette: () => set((s) => ({ paletteOpen: !s.paletteOpen, settingsOpen: false })),

  openShortcuts: () => set({ shortcutsOpen: true }),
  closeShortcuts: () => set({ shortcutsOpen: false }),

  toggleSettings: () => set((s) => ({ settingsOpen: !s.settingsOpen })),
  closeSettings: () => set({ settingsOpen: false }),

  openEntity: (entity) => set({ entity }),
  closeEntity: () => set({ entity: null }),
}));

/** Call once before first paint so there is no theme flash. */
applyAppearance(initialAccent, initialTheme);

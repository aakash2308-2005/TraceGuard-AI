import { useUi, ACCENTS, ACCENT_LABEL, type Accent, type ThemeMode } from "../state/ui";
import { IconKeyboard, IconMoon, IconSun } from "./icons";

const THEME_OPTIONS: { mode: ThemeMode; label: string; icon: React.ReactNode }[] = [
  { mode: "dark", label: "Dark", icon: <IconMoon size={15} /> },
  { mode: "light", label: "Light", icon: <IconSun size={15} /> },
];

/** Appearance controls: accent colour + light/dark, both persisted. */
export function SettingsPopover() {
  const open = useUi((s) => s.settingsOpen);
  const close = useUi((s) => s.closeSettings);
  const accent = useUi((s) => s.accent);
  const setAccent = useUi((s) => s.setAccent);
  const theme = useUi((s) => s.theme);
  const setTheme = useUi((s) => s.setTheme);
  const openShortcuts = useUi((s) => s.openShortcuts);

  if (!open) return null;

  return (
    <>
      <div className="tg-popover-scrim" role="presentation" onMouseDown={close} />
      <div className="tg-popover" role="dialog" aria-label="Appearance settings">
        <div className="tg-popover-head">Appearance</div>

        <fieldset className="tg-picker">
          <legend>Accent</legend>
          <div className="tg-accent-row">
            {ACCENTS.map((a: Accent) => (
              <button
                key={a}
                type="button"
                className={`tg-accent-swatch tg-swatch-${a}`}
                aria-pressed={accent === a}
                aria-label={`${ACCENT_LABEL[a]} accent`}
                title={ACCENT_LABEL[a]}
                onClick={() => setAccent(a)}
              >
                {accent === a && <span aria-hidden="true">✓</span>}
              </button>
            ))}
          </div>
        </fieldset>

        <fieldset className="tg-picker">
          <legend>Theme</legend>
          <div className="tg-segmented">
            {THEME_OPTIONS.map((o) => (
              <button
                key={o.mode}
                type="button"
                aria-pressed={theme === o.mode}
                onClick={() => setTheme(o.mode)}
              >
                {o.icon}
                {o.label}
              </button>
            ))}
          </div>
        </fieldset>

        <button
          type="button"
          className="tg-popover-link"
          onClick={() => {
            close();
            openShortcuts();
          }}
        >
          <IconKeyboard size={15} />
          Keyboard shortcuts
          <kbd className="tg-kbd">?</kbd>
        </button>
      </div>
    </>
  );
}

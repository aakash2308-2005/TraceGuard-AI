import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocation, useNavigate } from "react-router-dom";
import { listCases } from "../api/endpoints";
import { useAuth } from "../state/auth";
import { useUi } from "../state/ui";
import {
  IconClock,
  IconFolder,
  IconGraph,
  IconGrid,
  IconInfo,
  IconKeyboard,
  IconLogout,
  IconMoon,
  IconPlus,
  IconScroll,
  IconSearch,
  IconSun,
  IconUsers,
} from "./icons";

interface Command {
  id: string;
  group: string;
  label: string;
  hint?: string;
  icon: React.ReactNode;
  keywords?: string;
  run: () => void;
}

/** Case-sensitive prefix beats, then substring — keeps results predictable. */
function score(query: string, text: string): number {
  if (!query) return 1;
  const q = query.toLowerCase();
  const t = text.toLowerCase();
  if (t.startsWith(q)) return 100 - t.indexOf(q);
  const idx = t.indexOf(q);
  if (idx >= 0) return 50 - Math.min(idx, 40);
  // loose subsequence match so "dg" finds "Dashboard"
  let qi = 0;
  for (let i = 0; i < t.length && qi < q.length; i++) if (t[i] === q[qi]) qi++;
  return qi === q.length ? 10 : 0;
}

export function CommandPalette() {
  const open = useUi((s) => s.paletteOpen);
  const close = useUi((s) => s.closePalette);
  const theme = useUi((s) => s.theme);
  const setTheme = useUi((s) => s.setTheme);
  const openShortcuts = useUi((s) => s.openShortcuts);
  const navigate = useNavigate();
  const location = useLocation();
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);

  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const { data: cases } = useQuery({
    queryKey: ["cases"],
    queryFn: listCases,
    enabled: open,
    staleTime: 60_000,
  });

  
  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      
      const id = requestAnimationFrame(() => inputRef.current?.focus());
      return () => cancelAnimationFrame(id);
    }
    return undefined;
  }, [open]);

  const caseId = /\/app\/cases\/([^/?#]+)/.exec(location.pathname)?.[1];
  const investigationId = /\/app\/investigations\/([^/?#]+)/.exec(location.pathname)?.[1];

  const commands = useMemo<Command[]>(() => {
    const go = (to: string) => () => {
      close();
      navigate(to);
    };

    const nav: Command[] = [
      { id: "nav-dashboard", group: "Go to", label: "Dashboard", icon: <IconGrid size={16} />, keywords: "home overview", run: go("/app") },
      { id: "nav-investigate", group: "Go to", label: "Investigate", icon: <IconPlus size={16} />, run: go("/app/investigate") },
      { id: "nav-cases", group: "Go to", label: "Cases", icon: <IconFolder size={16} />, run: go("/app/cases") },
      { id: "nav-help", group: "Go to", label: "Help", hint: "Epistemic status reference", icon: <IconInfo size={16} />, run: go("/app/audit-help") },
      ...(user?.permissions?.manage_users
        ? [{ id: "nav-admin", group: "Go to", label: "Administration", icon: <IconUsers size={16} />, run: go("/app/admin") } satisfies Command]
        : []),
    ];

    const ctx: Command[] = [];
    if (caseId) {
      ctx.push(
        { id: "ctx-graph", group: "This case", label: "Relationship graph", icon: <IconGraph size={16} />, run: go(`/app/cases/${caseId}/graph`) },
        { id: "ctx-timeline", group: "This case", label: "Case timeline", icon: <IconClock size={16} />, run: go(`/app/cases/${caseId}/timeline`) },
        { id: "ctx-audit", group: "This case", label: "Case audit trail", icon: <IconScroll size={16} />, run: go(`/app/cases/${caseId}/audit`) },
        { id: "ctx-open", group: "This case", label: "Open case detail", icon: <IconFolder size={16} />, run: go(`/app/cases/${caseId}`) },
      );
    }
    if (investigationId) {
      ctx.push(
        { id: "ctx-inv", group: "This investigation", label: "Open investigation", icon: <IconScroll size={16} />, run: go(`/app/investigations/${investigationId}`) },
        { id: "ctx-conf", group: "This investigation", label: "Confidence & limitations", icon: <IconGraph size={16} />, run: go(`/app/investigations/${investigationId}?tab=confidence`) },
      );
    }

    const actions: Command[] = [
      {
        id: "act-theme",
        group: "Actions",
        label: theme === "dark" ? "Switch to light theme" : "Switch to dark theme",
        icon: theme === "dark" ? <IconSun size={16} /> : <IconMoon size={16} />,
        run: () => {
          setTheme(theme === "dark" ? "light" : "dark");
          close();
        },
      },
      {
        id: "act-keys",
        group: "Actions",
        label: "Keyboard shortcuts",
        hint: "?",
        icon: <IconKeyboard size={16} />,
        run: () => {
          close();
          openShortcuts();
        },
      },
      {
        id: "act-logout",
        group: "Actions",
        label: "Sign out",
        icon: <IconLogout size={16} />,
        run: () => {
          close();
          logout();
          navigate("/login");
        },
      },
    ];

    const caseCmds: Command[] = (cases ?? []).map((c) => ({
      id: `case-${c.id}`,
      group: "Cases",
      label: c.title,
      hint: c.status.replace(/_/g, " "),
      icon: <IconFolder size={16} />,
      keywords: c.description ?? "",
      run: go(`/app/cases/${c.id}`),
    }));

    return [...nav, ...ctx, ...caseCmds, ...actions];
  }, [caseId, investigationId, cases, theme, user, close, navigate, logout, openShortcuts, setTheme]);

  const results = useMemo(() => {
    const scored = commands
      .map((c) => ({ c, s: Math.max(score(query, c.label), score(query, c.group), score(query, c.keywords ?? "")) }))
      .filter((x) => x.s > 0)
      .sort((a, b) => b.s - a.s);
    return scored.slice(0, 10).map((x) => x.c);
  }, [commands, query]);

  useEffect(() => {
    setActive((a) => (a >= results.length ? 0 : a));
  }, [results.length]);

  // Keep the highlighted row visible when arrowing past the fold.
  useEffect(() => {
    if (!open) return;
    const el = listRef.current?.querySelector<HTMLElement>('[data-active="true"]');
    el?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  if (!open) return null;

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => (results.length ? (a + 1) % results.length : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => (results.length ? (a - 1 + results.length) % results.length : 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      results[active]?.run();
    } else if (e.key === "Escape") {
      e.preventDefault();
      close();
    }
  };

  let lastGroup = "";

  return (
    <div className="tg-overlay" role="presentation" onMouseDown={close}>
      <div
        className="tg-palette"
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="tg-palette-input">
          <IconSearch size={17} />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
            onKeyDown={onKey}
            placeholder="Search cases, jump to a page, run a command…"
            aria-label="Command palette search"
            aria-controls="tg-palette-list"
            aria-activedescendant={results[active]?.id}
            role="combobox"
            aria-expanded="true"
            autoComplete="off"
            spellCheck={false}
          />
          <kbd className="tg-kbd">esc</kbd>
        </div>

        <div className="tg-palette-list" id="tg-palette-list" role="listbox" ref={listRef}>
          {results.length === 0 && (
            <div className="tg-palette-empty">
              <IconSearch size={18} />
              No matches for “{query}”
            </div>
          )}
          {results.map((c, i) => {
            const header = c.group !== lastGroup ? c.group : null;
            lastGroup = c.group;
            return (
              <div key={c.id}>
                {header && <div className="tg-palette-group">{header}</div>}
                <button
                  type="button"
                  id={c.id}
                  role="option"
                  aria-selected={i === active}
                  data-active={i === active}
                  className="tg-palette-item"
                  onMouseEnter={() => setActive(i)}
                  onClick={c.run}
                >
                  <span className="tg-palette-icon" aria-hidden="true">
                    {c.icon}
                  </span>
                  <span className="tg-palette-label">{c.label}</span>
                  {c.hint && <span className="tg-palette-hint">{c.hint}</span>}
                </button>
              </div>
            );
          })}
        </div>

        <div className="tg-palette-foot">
          <span>
            <kbd className="tg-kbd">↑</kbd>
            <kbd className="tg-kbd">↓</kbd> navigate
          </span>
          <span>
            <kbd className="tg-kbd">↵</kbd> open
          </span>
          <span>
            <kbd className="tg-kbd">esc</kbd> close
          </span>
          <span className="tg-palette-foot-status">
            {cases ? `${cases.length} case${cases.length === 1 ? "" : "s"} indexed` : "indexing…"}
          </span>
        </div>
      </div>
    </div>
  );
}

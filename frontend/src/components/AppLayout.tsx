import { useCallback, useEffect, useMemo, useRef, useState, type ComponentType } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../state/auth";
import { useUi } from "../state/ui";
import { useGlobalShortcuts } from "../hooks/useGlobalShortcuts";
import { Button, Pill } from "./common";
import { CommandPalette } from "./CommandPalette";
import { EntityDrawer } from "./EntityDrawer";
import { SettingsPopover } from "./SettingsPopover";
import { ShortcutsHelp } from "./ShortcutsHelp";
import { Toaster } from "./Toaster";
import {
  IconFolder,
  IconGrid,
  IconInfo,
  IconKeyboard,
  IconLogout,
  IconMenu,
  IconMoon,
  IconSearch,
  IconTarget,
  IconSettings,
  IconSun,
  IconUsers,
  Logo,
  type IconProps,
} from "./icons";
import { initialsOf, titleCase } from "../utils/format";

interface NavItem {
  to: string;
  label: string;
  end?: boolean;
  icon: ComponentType<IconProps>;
}

interface NavGroup {
  group: string;
  items: NavItem[];
}

export function AppLayout() {
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  const navigate = useNavigate();
  const location = useLocation();

  const theme = useUi((s) => s.theme);
  const toggleTheme = useUi((s) => s.toggleTheme);
  const openPalette = useUi((s) => s.openPalette);
  const toggleSettings = useUi((s) => s.toggleSettings);
  const settingsOpen = useUi((s) => s.settingsOpen);
  const openShortcuts = useUi((s) => s.openShortcuts);

  useGlobalShortcuts();

  const lastScrollTopRef = useRef(0);
  const [topbarHidden, setTopbarHidden] = useState(false);

  // Slide-out nav drawer
  const [navOpen, setNavOpen] = useState<boolean>(() => {
    const stored = localStorage.getItem("tg_nav_open");
    if (stored === "1") return true;
    if (stored === "0") return false;
    return typeof window !== "undefined" && window.matchMedia("(min-width: 960px)").matches;
  });
  useEffect(() => {
    localStorage.setItem("tg_nav_open", navOpen ? "1" : "0");
  }, [navOpen]);
  const closeNav = useCallback(() => setNavOpen(false), []);
  //On mobile the drawer overlays the content, so any navigation closes it.
  useEffect(() => {
    if (typeof window !== "undefined" && window.matchMedia("(max-width: 959px)").matches) {
      setNavOpen(false);
    }
  }, [location.pathname]);

  // Reset the browser page scroll on navigation so deep links open at the top.
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "auto" });
    lastScrollTopRef.current = 0;
    setTopbarHidden(false);
  }, [location.pathname]);

  useEffect(() => {
    const onScroll = () => {
      const scrollTop = window.scrollY;
      const scrollingDown = scrollTop > lastScrollTopRef.current;
      setTopbarHidden(scrollTop > 8 && scrollingDown);
      lastScrollTopRef.current = scrollTop;
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

 
  const modKey = useMemo(
    () => (/Mac|iPhone|iPad/.test(navigator.userAgent) ? "⌘" : "Ctrl"),
    [],
  );

  const onLogout = () => {
    logout();
    navigate("/login");
  };

  const groups: NavGroup[] = [
    {
      group: "Investigate",
      items: [
        { to: "/app", label: "Dashboard", end: true, icon: IconGrid },
        { to: "/app/investigate", label: "Investigate", icon: IconTarget },
        { to: "/app/cases", label: "Cases", icon: IconFolder },
      ],
    },
    {
      group: "Governance",
      items: [
        { to: "/app/audit-help", label: "Help", icon: IconInfo },
        ...(user?.permissions?.manage_users
          ? [{ to: "/app/admin", label: "Administration", icon: IconUsers } satisfies NavItem]
          : []),
      ],
    },
  ];

  return (
    <div
      className={`tg-shell ${navOpen ? "tg-nav-open" : "tg-nav-closed"} ${
        topbarHidden ? "tg-topbar-hidden" : ""
      }`}
    >
      <aside className="tg-sidebar">
        <Link to="/app" className="tg-brand-row">
          <Logo size={36} />
          <span>
            <div className="tg-brand">
              Trace<span>Guard</span> AI
            </div>
            <div className="tg-tagline">Connect. Analyze. Uncover.</div>
          </span>
        </Link>

        <nav className="tg-nav" aria-label="Primary">
          {groups.map((g) => (
            <div key={g.group}>
              <div className="tg-nav-group-label">{g.group}</div>
              {g.items.map((n) => {
                const Icon = n.icon;
                return (
                  <NavLink key={n.to} to={n.to} end={n.end} onClick={closeNav}>
                    <span className="tg-nav-icon">
                      <Icon size={18} />
                    </span>
                    {n.label}
                  </NavLink>
                );
              })}
            </div>
          ))}
        </nav>

        <div className="tg-sidebar-footer">
          <div className="tg-user-card">
            <span className="tg-avatar" aria-hidden="true">
              {initialsOf(user?.username)}
            </span>
            <div className="tg-user-meta">
              <div className="tg-user-name">{user?.username ?? "—"}</div>
              <div className="tg-list-meta">{titleCase(user?.role)}</div>
            </div>
          </div>
          <Button variant="ghost" icon={<IconLogout size={16} />} fullWidth onClick={onLogout}>
            Sign out
          </Button>
        </div>
      </aside>

      {/* Overlay scrim */}
      {navOpen && (
        <button
          type="button"
          className="tg-nav-scrim"
          aria-label="Close navigation"
          onClick={closeNav}
        />
      )}

      <div className="tg-main">
        <header className="tg-topbar">
          <button
            type="button"
            className="tg-nav-toggle"
            onClick={() => setNavOpen((v) => !v)}
            aria-label={navOpen ? "Collapse navigation" : "Expand navigation"}
            aria-expanded={navOpen}
            title="Menu"
          >
            <IconMenu size={18} />
          </button>
          <div className="tg-topbar-actions">
            <button type="button" className="tg-search-trigger" onClick={openPalette}>
              <IconSearch size={15} aria-hidden="true" />
              <span className="tg-search-trigger-text">Search…</span>
              <kbd className="tg-kbd">{modKey} K</kbd>
            </button>

            <button
              type="button"
              className="tg-icon-btn"
              onClick={toggleTheme}
              aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
              title={theme === "dark" ? "Light theme (t)" : "Dark theme (t)"}
            >
              {theme === "dark" ? <IconSun size={16} /> : <IconMoon size={16} />}
            </button>

            <button
              type="button"
              className="tg-icon-btn"
              onClick={openShortcuts}
              aria-label="Keyboard shortcuts"
              title="Keyboard shortcuts (?)"
            >
              <IconKeyboard size={16} />
            </button>

            <div className="tg-anchor">
              <button
                type="button"
                className="tg-icon-btn"
                onClick={toggleSettings}
                aria-expanded={settingsOpen}
                aria-haspopup="dialog"
                aria-label="Appearance settings"
                title="Appearance settings"
              >
                <IconSettings size={16} />
              </button>
              <SettingsPopover />
            </div>

            <Pill tone="info">{titleCase(user?.role)}</Pill>
          </div>
        </header>

        
        <div className="tg-content">
          <div className="tg-page" key={location.pathname}>
            <Outlet />
          </div>
        </div>
      </div>

      {/* App-wide surfaces */}
      <Toaster />
      <CommandPalette />
      <ShortcutsHelp />
      <EntityDrawer />
    </div>
  );
}

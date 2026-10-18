import type { ReactNode } from "react";
import { IconAlert, IconCheckCircle, IconSearch } from "./icons";
import { useCountUp } from "../hooks/useCountUp";
import type { Tone } from "../utils/status";
import { statusTone } from "../utils/status";

export type BoxTone = "violet" | "blue" | "cyan" | "slate";

export function Card({
  children,
  title,
  subtitle,
  actions,
  icon,
  className = "",
  bodyClassName = "",
  tone,
}: {
  children: ReactNode;
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  icon?: ReactNode;
  className?: string;
  bodyClassName?: string;
  
  tone?: BoxTone;
}) {
  const hasHead = Boolean(title || subtitle || actions);
  const classes = ["tg-card", tone ? `tg-tone-${tone}` : "", className]
    .filter(Boolean)
    .join(" ");
  return (
    <section className={classes}>
      {hasHead && (
        <header className="tg-card-head">
          <div className="tg-card-head-text">
            {title && (
              <h2 className="tg-card-title">
                {icon && <span className="tg-card-title-icon">{icon}</span>}
                {title}
              </h2>
            )}
            {subtitle && <div className="tg-card-subtitle">{subtitle}</div>}
          </div>
          {actions && <div className="tg-card-actions">{actions}</div>}
        </header>
      )}
      <div className={`tg-card-body ${bodyClassName}`.trim()}>{children}</div>
    </section>
  );
}

/* ---------------------------------------------------------- Page header ---- */

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="tg-page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <div className="tg-page-subtitle">{subtitle}</div>}
      </div>
      {actions && <div className="tg-page-actions">{actions}</div>}
    </header>
  );
}

/* ------------------------------------------------------------- States ----- */

export function EmptyState({
  message,
  title,
  icon,
  action,
  steps,
}: {
  message: string;
  title?: string;
  icon?: ReactNode;
  action?: ReactNode;
  
  steps?: { label: string; detail?: string; onClick?: () => void }[];
}) {
  return (
    <div className="tg-empty" role="status">
      <span className="tg-empty-icon">{icon ?? <IconSearch size={22} />}</span>
      {title && <div className="tg-empty-title">{title}</div>}
      <div className="tg-empty-message">{message}</div>
      {steps && steps.length > 0 && (
        <ol className="tg-steps">
          {steps.map((s, i) => (
            <li key={s.label}>
              <span className="tg-step-num" aria-hidden="true">
                {i + 1}
              </span>
              <span className="tg-step-body">
                <span className="tg-step-label">{s.label}</span>
                {s.detail && <span className="tg-step-detail">{s.detail}</span>}
              </span>
              {s.onClick && (
                <button type="button" className="tg-step-action" onClick={s.onClick}>
                  Start
                </button>
              )}
            </li>
          ))}
        </ol>
      )}
      {action}
    </div>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="tg-loading" role="status" aria-live="polite">
      <span className="tg-spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function Skeleton({ width = "100%", height = 14 }: { width?: string; height?: number }) {
  return (
    <span
      className="tg-skeleton"
      aria-hidden="true"
      style={{ display: "block", width, height }}
    />
  );
}

export function Banner({
  children,
  tone = "error",
  icon,
}: {
  children: ReactNode;
  tone?: "error" | "success";
  icon?: ReactNode;
}) {
  const isError = tone === "error";
  return (
    <div className={`tg-banner ${isError ? "tg-banner-error" : "tg-banner-success"}`} role={isError ? "alert" : "status"}>
      <span className="tg-banner-icon">
        {icon ?? (isError ? <IconAlert size={16} /> : <IconCheckCircle size={16} />)}
      </span>
      <span>{children}</span>
    </div>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return <Banner tone="error">{message}</Banner>;
}

/* -------------------------------------------------------------- Button ----- */

export type ButtonVariant = "default" | "primary" | "danger" | "ghost";

export function Button({
  children,
  onClick,
  disabled,
  type = "button",
  variant = "default",
  size = "md",
  icon,
  fullWidth,
  title,
  ariaLabel,
}: {
  children?: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  type?: "button" | "submit";
  variant?: ButtonVariant;
  size?: "sm" | "md" | "lg";
  icon?: ReactNode;
  fullWidth?: boolean;
  title?: string;
  ariaLabel?: string;
}) {
  const classes = [
    "tg-button",
    variant !== "default" ? `tg-button-${variant}` : "",
    size !== "md" ? `tg-button-${size}` : "",
    fullWidth ? "tg-button-full" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      className={classes}
      onClick={onClick}
      disabled={disabled}
      type={type}
      title={title}
      aria-label={ariaLabel}
    >
      {icon}
      {children}
    </button>
  );
}

/* ---------------------------------------------------------------- Pills ---- */

export function Pill({
  children,
  tone = "neutral",
  dot = false,
}: {
  children: ReactNode;
  tone?: Tone;
  dot?: boolean;
}) {
  return (
    <span className={`tg-pill tg-pill-${tone}`}>
      {dot && <span className="tg-dot" aria-hidden="true" />}
      {children}
    </span>
  );
}

export function StatusPill({ value }: { value: string }) {
  return <Pill tone={statusTone(value)}>{String(value).replace(/_/g, " ")}</Pill>;
}

/* ---------------------------------------------------------------- Table ---- */

export function DataTable({
  columns,
  rows,
  empty,
}: {
  columns: ReactNode[];
  rows: (string | ReactNode)[][];
  empty?: ReactNode;
}) {
  if (rows.length === 0 && empty) {
    return <>{empty}</>;
  }
  return (
    <div className="tg-table-wrap">
      <table className="tg-table">
        <thead>
          <tr>
            {columns.map((c, i) => (
              <th key={i}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ----------------------------------------------------------------- Tabs ---- */

export function Tabs({
  tabs,
  active,
  onChange,
  ariaLabel = "Sections",
}: {
  tabs: { id: string; label: string; count?: number }[];
  active: string;
  onChange: (id: string) => void;
  ariaLabel?: string;
}) {
  return (
    <div className="tg-tabs" role="tablist" aria-label={ariaLabel}>
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          role="tab"
          className="tg-tab"
          aria-selected={active === t.id}
          onClick={() => onChange(t.id)}
        >
          {t.label}
          {t.count != null && <span className="tg-tab-count">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

/* ----------------------------------------------------------------- Misc ---- */

export function Note({ children, icon }: { children: ReactNode; icon?: ReactNode }) {
  return (
    <div className="tg-note">
      <span className="tg-note-icon">{icon}</span>
      <span>{children}</span>
    </div>
  );
}

export function Stat({
  label,
  value,
  icon,
  hint,
  tone,
  variant = "row",
  detail,
  delta,
}: {
  label: string;
  value: ReactNode;
  icon?: ReactNode;
  hint?: ReactNode;
  
  tone?: BoxTone;
  variant?: "row" | "panel";
  detail?: ReactNode;
  delta?: ReactNode;
}) {
 
  const animated = useCountUp(typeof value === "number" ? value : 0);
  const shown = typeof value === "number" ? animated : value;

  if (variant === "panel") {
    return (
      <div className={`tg-stat tg-stat-panel${tone ? ` tg-tone-${tone}` : ""}`}>
        <div className="tg-stat-head">
          {icon && <span className="tg-stat-icon">{icon}</span>}
          <span className="tg-stat-label">{label}</span>
        </div>
        <div className="tg-stat-main">
          <div className="tg-stat-value">{shown}</div>
          {detail && <div className="tg-stat-detail">{detail}</div>}
        </div>
        {delta && <div className="tg-stat-delta">{delta}</div>}
        {hint && <div className="tg-stat-hint">{hint}</div>}
      </div>
    );
  }

  return (
    <div className={`tg-stat${tone ? ` tg-tone-${tone}` : ""}`}>
      {icon && <span className="tg-stat-icon">{icon}</span>}
      <div>
        <div className="tg-stat-value">{shown}</div>
        <div className="tg-stat-label">{label}</div>
        {hint && <div className="tg-stat-hint">{hint}</div>}
      </div>
    </div>
  );
}

export function Field({
  label,
  htmlFor,
  hint,
  children,
}: {
  label: string;
  htmlFor?: string;
  hint?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="tg-field">
      <label className="tg-label" htmlFor={htmlFor}>
        {label}
      </label>
      {children}
      {hint && <div className="tg-hint">{hint}</div>}
    </div>
  );
}

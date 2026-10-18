import { useEffect, useState } from "react";
import { copyText } from "../utils/export";
import { IconCheck, IconCopy, IconXCircle } from "./icons";


export function CopyButton({
  value,
  label = "Copy",
  iconOnly = false,
  className = "",
  onCopied,
}: {
  value: string;
  label?: string;
  iconOnly?: boolean;
  className?: string;
  onCopied?: () => void;
}) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");

  useEffect(() => {
    if (state === "idle") return undefined;
    const id = window.setTimeout(() => setState("idle"), 1800);
    return () => window.clearTimeout(id);
  }, [state]);

  const run = async () => {
    const ok = await copyText(value);
    setState(ok ? "copied" : "failed");
    if (ok) onCopied?.();
  };

  const text = state === "copied" ? "Copied" : state === "failed" ? "Press ⌘C" : label;

  return (
    <button
      type="button"
      className={`tg-copy-btn ${state === "copied" ? "is-copied" : ""} ${iconOnly ? "tg-copy-icon" : ""} ${className}`.trim()}
      onClick={() => void run()}
      aria-label={iconOnly ? `Copy ${label.toLowerCase()}` : label}
      title={iconOnly ? label : undefined}
    >
      <span aria-hidden="true">
        {state === "copied" ? (
          <IconCheck size={14} />
        ) : state === "failed" ? (
          <IconXCircle size={14} />
        ) : (
          <IconCopy size={14} />
        )}
      </span>
      {!iconOnly && <span>{text}</span>}
      <span className="tg-sr-only" aria-live="polite">
        {state === "copied" ? "Copied to clipboard" : state === "failed" ? "Copy failed" : ""}
      </span>
    </button>
  );
}

import { useEffect, useRef } from "react";
import { useToasts, type ToastItem } from "../state/toast";
import { IconAlert, IconCheckCircle, IconInfo, IconX } from "./icons";

const TONE_ICON = {
  success: <IconCheckCircle size={17} />,
  error: <IconAlert size={17} />,
  info: <IconInfo size={17} />,
};

const AUTO_DISMISS_MS = 5000;

function ToastCard({ item }: { item: ToastItem }) {
  const dismiss = useToasts((s) => s.dismiss);
  const timer = useRef<number | undefined>(undefined);
  const paused = useRef(false);

  useEffect(() => {
    timer.current = window.setTimeout(() => {
      if (!paused.current) dismiss(item.id);
    }, AUTO_DISMISS_MS);
    return () => window.clearTimeout(timer.current);
  }, [item.id, dismiss]);

  return (
    <div
      className={`tg-toast tg-toast-${item.tone}`}
      role={item.tone === "error" ? "alert" : "status"}
      // Pausing on hover/focus keeps a long message readable before it leaves.
      onMouseEnter={() => {
        paused.current = true;
        window.clearTimeout(timer.current);
      }}
      onMouseLeave={() => {
        paused.current = false;
        timer.current = window.setTimeout(() => dismiss(item.id), AUTO_DISMISS_MS);
      }}
      onFocusCapture={() => {
        paused.current = true;
        window.clearTimeout(timer.current);
      }}
    >
      <span className="tg-toast-icon" aria-hidden="true">
        {TONE_ICON[item.tone]}
      </span>
      <div className="tg-toast-body">
        <div className="tg-toast-title">{item.title}</div>
        {item.description && <div className="tg-toast-desc">{item.description}</div>}
      </div>
      <button
        type="button"
        className="tg-toast-close"
        aria-label={`Dismiss: ${item.title}`}
        onClick={() => dismiss(item.id)}
      >
        <IconX size={14} />
      </button>
      <span className="tg-toast-progress" aria-hidden="true" />
    </div>
  );
}

export function Toaster() {
  const toasts = useToasts((s) => s.toasts);
  if (toasts.length === 0) return null;
  return (
    <div className="tg-toaster" aria-live="polite" aria-relevant="additions text">
      {toasts.map((t) => (
        <ToastCard key={t.id} item={t} />
      ))}
    </div>
  );
}

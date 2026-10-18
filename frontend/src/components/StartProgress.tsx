import { useEffect, useRef, useState } from "react";
import { IconAlert, IconCheck, IconSparkles } from "./icons";

/**
 * Animated launch sequence shown while an investigation is being created.
 *
 * The staged narration is cosmetic: the API response (`ready`) is the only
 * thing that completes the run. Progress eases toward a floor while the
 * request is in flight and only finishes once the backend has actually
 * created the run, so the UI never claims success early. A failed request
 * freezes the bar and surfaces the error inline instead of navigating.
 */

const STEPS = [
  { label: "Validating case evidence", detail: "Schema, custody and permission checks" },
  { label: "Fingerprinting artifacts", detail: "SHA-256 hash for every evidence item" },
  { label: "Planning the run", detail: "Selecting agents for this evidence mix" },
  { label: "Dispatching the pipeline", detail: "Content → OSINT → metadata → crypto" },
  { label: "Run created", detail: "Phase progress streams in the run view" },
] as const;

/** Cosmetic timing: one tick per staged step while the request is in flight. */
const STEP_MS = 800;
const TOTAL_MS = STEP_MS * STEPS.length;
/** Where the bar parks while waiting on the backend (never reaches 100%). */
const WAIT_FLOOR = 88;
/** Short pause at 100% so the "done" state is actually visible. */
const FINISH_HOLD_MS = 480;

export function StartProgress({
  open,
  ready = false,
  title = "Starting investigation",
  readyDetail = "Opening the live run view…",
  error = null,
  onComplete,
  onClose,
}: {
  open: boolean;
  ready?: boolean;
  title?: string;
  readyDetail?: string;
  error?: string | null;
  /** Fires once the bar has reached 100% and the hold has elapsed. */
  onComplete?: () => void;
  /** Dismiss (error state only) — the caller resets the mutation. */
  onClose?: () => void;
}) {
  const [progress, setProgress] = useState(0);
  const [step, setStep] = useState(0);

  // Mirror props into refs so the animation loop never needs restarting (and
  // never captures a stale callback).
  const readyRef = useRef(ready);
  const errorRef = useRef(error);
  const completeRef = useRef(onComplete);
  const closeRef = useRef(onClose);
  readyRef.current = ready;
  errorRef.current = error;
  completeRef.current = onComplete;
  closeRef.current = onClose;

  // Escape dismisses the error state (nothing else is dismissible).
  useEffect(() => {
    if (!open || !error) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeRef.current?.();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, error]);

  useEffect(() => {
    if (!open) return;

    let raf = 0;
    let hold = 0;
    let value = 0;
    let finished = false;
    let last = performance.now();
    const start = last;

    setProgress(0);
    setStep(0);

    const tick = (now: number) => {
      const dt = Math.min(now - last, 150);
      last = now;
      const elapsed = now - start;
      const failed = Boolean(errorRef.current);

      const target = failed
        ? value // freeze where the failure happened
        : readyRef.current
          ? 100
          : Math.min(WAIT_FLOOR, (elapsed / TOTAL_MS) * 100);

      // Frame-rate independent ease toward the target.
      value += (target - value) * (1 - Math.exp(-dt / (target === 100 ? 130 : 320)));
      if (target === 100 && value > 99.3) value = 100;

      setProgress(value);
      // The final step is only claimed once the run actually exists — a slow
      // request parks on the previous step instead of announcing success.
      if (!failed) {
        const cap = readyRef.current ? STEPS.length - 1 : STEPS.length - 2;
        setStep(Math.max(0, Math.min(cap, Math.floor(elapsed / STEP_MS))));
      }

      if (value >= 100 && !finished) {
        finished = true;
        hold = window.setTimeout(() => completeRef.current?.(), FINISH_HOLD_MS);
        return;
      }
      raf = requestAnimationFrame(tick);
    };

    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      window.clearTimeout(hold);
    };
  }, [open]);

  if (!open) return null;

  const failed = Boolean(error);
  const done = ready && !failed;
  const icon = failed ? (
    <IconAlert size={22} />
  ) : done ? (
    <IconCheck size={22} />
  ) : (
    <IconSparkles size={22} />
  );

  return (
    <div
      className="tg-overlay tg-launch-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div className="tg-launch" role="status" aria-live="polite">
        <div
          className="tg-launch-orb"
          data-state={failed ? "error" : done ? "done" : "run"}
          aria-hidden="true"
        >
          <span className="tg-launch-orb-ring" />
          <span className="tg-launch-orb-ring tg-launch-orb-ring-late" />
          <span className="tg-launch-orb-core">{icon}</span>
        </div>

        <div className="tg-launch-title">
          {failed ? "Investigation could not start" : done ? "Run created" : title}
        </div>
        <div className="tg-launch-detail">
          {failed
            ? "The backend rejected the request — nothing was started."
            : done
              ? readyDetail
              : STEPS[step].detail}
        </div>

        <div className="tg-launch-track">
          <div
            className="tg-launch-fill"
            data-state={failed ? "error" : done ? "done" : "run"}
            style={{ width: `${progress}%` }}
          />
        </div>

        <div className="tg-launch-legend">
          <span className="tg-launch-pct">{Math.round(progress)}%</span>
          <span className="tg-launch-phase">
            {failed ? "Stopped" : done ? "Complete" : "Working…"}
          </span>
        </div>

        <ol className="tg-launch-steps">
          {STEPS.map((s, i) => {
            const state = failed
              ? i < step
                ? "done"
                : i === step
                  ? "failed"
                  : "todo"
              : done || i < step
                ? "done"
                : i === step
                  ? "now"
                  : "todo";
            return (
              <li key={s.label} data-state={state}>
                <span className="tg-launch-step-icon" aria-hidden="true">
                  {state === "done" ? "✓" : state === "failed" ? "✕" : i + 1}
                </span>
                <span className="tg-launch-step-body">
                  <span className="tg-launch-step-label">{s.label}</span>
                  <span className="tg-launch-step-detail">{s.detail}</span>
                </span>
              </li>
            );
          })}
        </ol>

        {failed && (
          <>
            <div className="tg-launch-error" role="alert">
              {error}
            </div>
            <button
              type="button"
              className="tg-button tg-button-full"
              onClick={onClose}
              autoFocus
            >
              Back
            </button>
          </>
        )}
      </div>
    </div>
  );
}

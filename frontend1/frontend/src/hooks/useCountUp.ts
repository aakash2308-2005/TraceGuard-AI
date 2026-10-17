import { useEffect, useRef, useState } from "react";

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
}

/** rAF is suspended in hidden tabs, so an animation would never advance. */
function canAnimate(): boolean {
  return (
    typeof document !== "undefined" &&
    document.visibilityState === "visible" &&
    !prefersReducedMotion()
  );
}

/**
 * Count a number up to its target over `durationMs` with an ease-out curve.
 * Starts from 0 on mount (so dashboard stats tick up when they appear) and
 * animates again if the target changes. Respects prefers-reduced-motion, and
 * skips straight to the value when the tab is hidden — otherwise the frame
 * callback never fires and the number would sit at 0 until you switch back.
 */
export function useCountUp(target: number, durationMs = 750): number {
  const isInt = Number.isInteger(target);
  const [display, setDisplay] = useState(() =>
    Number.isFinite(target) && canAnimate() ? 0 : target,
  );
  const fromRef = useRef(0);

  useEffect(() => {
    if (!Number.isFinite(target) || !canAnimate()) {
      fromRef.current = target;
      setDisplay(target);
      return undefined;
    }

    const from = fromRef.current;
    const start = performance.now();
    let frame = 0;
    let done = false;

    const finish = () => {
      if (done) return;
      done = true;
      fromRef.current = target;
      setDisplay(target);
    };

    const step = (now: number) => {
      if (done) return;
      const t = Math.min(1, (now - start) / durationMs);
      if (t >= 1) {
        finish();
        return;
      }
      const eased = 1 - Math.pow(1 - t, 3);
      const next = from + (target - from) * eased;
      setDisplay(isInt ? Math.round(next) : next);
      frame = requestAnimationFrame(step);
    };

    frame = requestAnimationFrame(step);
    // Belt and braces: if frames are suspended (tab hidden mid-animation) the
    // timeout still lands on the final value instead of freezing.
    const safety = window.setTimeout(finish, durationMs + 400);

    return () => {
      done = true;
      cancelAnimationFrame(frame);
      window.clearTimeout(safety);
      fromRef.current = target;
    };
  }, [target, durationMs, isInt]);

  return display;
}

import { FormEvent, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../state/auth";
import { toApiError } from "../api/client";
import { Button, Banner, Field } from "../components/common";
import { IconCheck, IconEye, IconEyeOff, IconLock, IconUser, Logo } from "../components/icons";

const FEATURES = [
  "Auto-extract IOCs from uploaded evidence",
  "Multi-agent analysis with provenance tracking",
  "Epistemic labelling — facts never blur into inference",
  "Hash-chained, tamper-evident audit trail",
];

export function LoginPage() {
  const login = useAuth((s) => s.login);
  const loading = useAuth((s) => s.loading);
  const navigate = useNavigate();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // The background eye watches the pointer: the pupil follows the cursor.
  const eyeRef = useRef<SVGSVGElement | null>(null);
  const lookRef = useRef<SVGGElement | null>(null);
  const beamRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const svg = eyeRef.current;
    const look = lookRef.current;
    const beam = beamRef.current;
    if (!svg || !look || !beam) return;
    // Reduced motion: the pupil simply rests in the centre.
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let raf = 0;
    let px = 0;
    let py = 0;
    const apply = () => {
      raf = 0;
      const r = svg.getBoundingClientRect();
      if (r.width === 0) return;
      const centerX = r.left + r.width / 2;
      const centerY = r.top + r.height / 2;
      const k = 120 / r.width; // screen px -> viewBox units
      let x = (px - centerX) * k * 0.3;
      let y = (py - centerY) * k * 0.3;
      const d = Math.hypot(x, y);
      const max = 15; // keep the pupil inside the white
      if (d > max) {
        x = (x / d) * max;
        y = (y / d) * max;
      }
      look.style.transform = `translate(${x.toFixed(2)}px, ${y.toFixed(2)}px)`;
      // Extend beyond the viewport so the cone reaches the window edge rather
      // than ending at the pointer.
      const beamLength = Math.hypot(window.innerWidth, window.innerHeight) * 1.5;
      const angle = Math.atan2(py - centerY, px - centerX) * (180 / Math.PI);
      beam.style.width = `${beamLength.toFixed(1)}px`;
      beam.style.transform = `translateY(-50%) rotate(${angle.toFixed(2)}deg)`;
    };
    const onMove = (e: PointerEvent) => {
      px = e.clientX;
      py = e.clientY;
      if (!raf) raf = requestAnimationFrame(apply);
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => {
      window.removeEventListener("pointermove", onMove);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await login(username, password);
      navigate("/app");
    } catch (err) {
      // Generic message avoids account enumeration.
      setError(toApiError(err).message || "Sign in failed");
    }
  };

  return (
    <main className="tg-login">
      {/* The watcher: one flat white eye behind everything; its pupil
          follows the pointer anywhere on the screen. Decorative only. */}
      <div className="tg-eye-bg" aria-hidden="true">
        <div ref={beamRef} className="tg-eye-beam" />
        <svg ref={eyeRef} className="tg-eye" viewBox="0 0 120 120">
          <g className="tg-eye-blink">
            <path className="tg-eye-white" d="M8 60C34 24 86 24 112 60 86 96 34 96 8 60Z" />
            <g ref={lookRef}>
              <circle className="tg-eye-pupil" cx="60" cy="60" r="15" />
            </g>
          </g>
        </svg>
      </div>

      <aside className="tg-login-aside">
        <div>
          <div className="tg-login-brand">
            <Logo size={44} />
            <div>
              <div className="tg-brand" style={{ fontSize: 20 }}>
                Trace<span>Guard</span> AI
              </div>
              <div className="tg-tagline">Connect. Analyze. Uncover.</div>
            </div>
          </div>

          <h1 className="tg-login-headline">
            Investigate cybercrime with evidence you can prove.
          </h1>
          <p className="tg-login-lede">
            A human-supervised investigation platform that correlates indicators, files, and
            on-chain data — while keeping verified facts strictly separate from AI inference.
          </p>

          <ul className="tg-login-features">
            {FEATURES.map((f) => (
              <li key={f}>
                <span className="tg-login-check">
                  <IconCheck size={14} />
                </span>
                {f}
              </li>
            ))}
          </ul>
        </div>

        <div className="tg-login-foot">
          Decision-support tool. Human-supervised. Not an autonomous decision-maker.
        </div>
      </aside>

      <section className="tg-login-panel">
        <form className="tg-login-form" onSubmit={onSubmit} noValidate={false}>
          <div className="tg-row tg-mt-2" style={{ gap: 8, marginBottom: 12 }}>
            <span className="tg-avatar" aria-hidden="true">
              <IconLock size={18} />
            </span>
            <div>
              <h1 style={{ margin: 0 }}>Sign in</h1>
              <div className="tg-subtle">Authenticate to access the workspace</div>
            </div>
          </div>

          <Field label="Username" htmlFor="username">
            <div className="tg-input-group">
              <input
                id="username"
                className="tg-input"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                required
                aria-label="Username"
              />
              <span className="tg-input-affix" aria-hidden="true" style={{ pointerEvents: "none" }}>
                <IconUser size={16} />
              </span>
            </div>
          </Field>

          <Field label="Password" htmlFor="password">
            <div className="tg-input-group">
              <input
                id="password"
                className="tg-input"
                type={show ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
                aria-label="Password"
              />
              <button
                type="button"
                className="tg-input-affix"
                onClick={() => setShow((s) => !s)}
                aria-label={show ? "Hide password" : "Show password"}
                title={show ? "Hide password" : "Show password"}
                style={{ position: "absolute" }}
              >
                {show ? <IconEyeOff size={16} /> : <IconEye size={16} />}
              </button>
            </div>
          </Field>

          {error && <Banner tone="error">{error}</Banner>}

          <Button type="submit" variant="primary" size="lg" fullWidth disabled={loading}>
            {loading ? "Signing in…" : "Sign in"}
          </Button>

          <div className="tg-demo-box">
            Demo credentials — <code>admin</code> / <code>ChangeMe123!</code>
          </div>
        </form>
      </section>
    </main>
  );
}

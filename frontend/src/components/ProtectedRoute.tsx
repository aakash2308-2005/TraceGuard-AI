import { useEffect } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../state/auth";
import { Loading } from "./common";

export function ProtectedRoute({ children }: { children: JSX.Element }) {
  const user = useAuth((s) => s.user);
  const initialized = useAuth((s) => s.initialized);
  const bootstrap = useAuth((s) => s.bootstrap);

  useEffect(() => {
    if (!initialized) void bootstrap();
  }, [initialized, bootstrap]);

  if (!initialized) {
    return <Loading label="Restoring session…" />;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

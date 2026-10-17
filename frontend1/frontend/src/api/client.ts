import axios, { AxiosError, AxiosInstance } from "axios";

// Base URL: in dev, Vite proxies "/api" to the backend. In the Docker demo,
// nginx proxies "/api" to the api service. VITE_API_BASE can override.
const baseURL = import.meta.env.VITE_API_BASE || "/api/v1";

export const api: AxiosInstance = axios.create({
  baseURL,
  timeout: 30_000,
});

// Attach bearer token from local storage on each request.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("tg_access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

// Normalize backend error envelope into a consistent shape for the UI.
export function toApiError(err: unknown): ApiError {
  if (axios.isAxiosError(err)) {
    const axiosErr = err as AxiosError<{ error?: ApiError }>;
    const envelope = axiosErr.response?.data?.error;
    if (envelope) return envelope;
    return {
      code: "network_error",
      message: axiosErr.message || "Network error",
    };
  }
  return { code: "unknown_error", message: "Unexpected error" };
}

// Unversioned health check (served at root, not under /api/v1).
export async function fetchHealth(): Promise<{ status: string; app: string }> {
  const res = await axios.get("/health");
  return res.data;
}

import { create } from "zustand";

/**
 * Toasts. Kept in a store (rather than React context) so any module —
 * endpoint wrappers, keyboard handlers, form submits — can raise one without
 * threading callbacks through props. The <Toaster /> host renders them.
 */

export type ToastTone = "success" | "error" | "info";

export interface ToastItem {
  id: number;
  tone: ToastTone;
  title: string;
  description?: string;
}

interface ToastState {
  toasts: ToastItem[];
  push: (toast: Omit<ToastItem, "id">) => void;
  dismiss: (id: number) => void;
}

let nextId = 1;

export const useToasts = create<ToastState>((set) => ({
  toasts: [],

  push: (item) => {
    const id = nextId++;
    set((s) => ({ toasts: [...s.toasts.slice(-3), { ...item, id }] }));
  },

  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

const push = (tone: ToastTone, title: string, description?: string) =>
  useToasts.getState().push({ tone, title, description });

export const toast = {
  success: (title: string, description?: string) => push("success", title, description),
  error: (title: string, description?: string) => push("error", title, description),
  info: (title: string, description?: string) => push("info", title, description),
};

/**
 * Map an unknown thrown value onto a readable toast. Axios errors carry the
 * API's message when available, which is far better than "Request failed".
 */
export function messageOf(err: unknown, fallback = "Something went wrong"): string {
  if (!err) return fallback;
  const anyErr = err as {
    response?: { data?: { detail?: unknown; message?: unknown } };
    message?: unknown;
  };
  const detail = anyErr.response?.data?.detail ?? anyErr.response?.data?.message;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (typeof anyErr.message === "string" && anyErr.message.trim()) return anyErr.message;
  return fallback;
}

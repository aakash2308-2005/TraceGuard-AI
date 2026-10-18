import { create } from "zustand";
import type { Me } from "../api/types";
import { getMe, login as apiLogin } from "../api/endpoints";

interface AuthState {
  user: Me | null;
  loading: boolean;
  initialized: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  bootstrap: () => Promise<void>;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  loading: false,
  initialized: false,

  login: async (username, password) => {
    set({ loading: true });
    try {
      const tokens = await apiLogin(username, password);
      localStorage.setItem("tg_access_token", tokens.access_token);
      localStorage.setItem("tg_refresh_token", tokens.refresh_token);
      const me = await getMe();
      set({ user: me, loading: false });
    } catch (err) {
      set({ loading: false });
      throw err;
    }
  },

  logout: () => {
    localStorage.removeItem("tg_access_token");
    localStorage.removeItem("tg_refresh_token");
    set({ user: null });
  },

  // Restore the session on page load if a token is present.
  bootstrap: async () => {
    const token = localStorage.getItem("tg_access_token");
    if (!token) {
      set({ initialized: true });
      return;
    }
    try {
      const me = await getMe();
      set({ user: me, initialized: true });
    } catch {
      localStorage.removeItem("tg_access_token");
      localStorage.removeItem("tg_refresh_token");
      set({ user: null, initialized: true });
    }
  },
}));

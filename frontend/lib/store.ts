import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { AuthResponse } from "./api";

interface AuthState {
  token: string | null;
  user: AuthResponse["user"] | null;
  team: AuthResponse["team"] | null;
  setAuth: (data: AuthResponse) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      team: null,
      setAuth: (data) => {
        localStorage.setItem("flakai_token", data.access_token);
        set({ token: data.access_token, user: data.user, team: data.team });
      },
      logout: () => {
        localStorage.removeItem("flakai_token");
        set({ token: null, user: null, team: null });
      },
    }),
    { name: "flakai-auth", partialize: (s) => ({ token: s.token, user: s.user, team: s.team }) }
  )
);

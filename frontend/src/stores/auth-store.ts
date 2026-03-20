import { create } from "zustand";
import { type User, initKeycloak, getMe, getAccessToken } from "@/lib/auth";

interface AuthState {
  user: User | null;
  loading: boolean;
  initialized: boolean;
  error: string | null;
  initAuth: () => Promise<void>;
  fetchUser: () => Promise<void>;
  setUser: (user: User | null) => void;
  clear: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  loading: true,
  initialized: false,
  error: null,
  initAuth: async () => {
    try {
      const authenticated = await initKeycloak();

      if (authenticated && getAccessToken()) {
        try {
          const user = await getMe();
          set({ user, loading: false, initialized: true });
        } catch (error) {
          console.error("initAuth - getMe failed:", error);
          const msg = error instanceof Error ? error.message : "Failed to load user profile";
          set({ user: null, loading: false, initialized: true, error: msg });
        }
      } else {
        set({ user: null, loading: false, initialized: true });
      }
    } catch (error) {
      console.error("initAuth error:", error);
      set({ user: null, loading: false, initialized: true, error: "Auth initialization failed" });
    }
  },
  fetchUser: async () => {
    set({ loading: true, error: null });
    try {
      const user = await getMe();
      set({ user, loading: false });
    } catch {
      set({ user: null, loading: false, error: "Not authenticated" });
    }
  },
  setUser: (user) => set({ user, loading: false }),
  clear: () => set({ user: null, loading: false, error: null }),
}));

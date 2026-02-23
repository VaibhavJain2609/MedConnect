import { create } from "zustand";
import { type User, initKeycloak, getMe } from "@/lib/auth";

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
      if (authenticated) {
        const user = await getMe();
        set({ user, loading: false, initialized: true });
      } else {
        set({ user: null, loading: false, initialized: true });
      }
    } catch {
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

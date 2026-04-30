import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import type { Role, User } from "./mockData";
import { loginAccessToken } from "@/services/authService";

interface AuthState {
  user: User | null;
  token: string | null;
  login: (email: string, role: Role, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

const STORAGE_KEY = "mediflow.auth";

type Session = { user: User; token: string; tokenType: string };

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(() => {
    if (typeof window === "undefined") return null;
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });

  const user = session?.user ?? null;
  const token = session?.token ?? null;

  const setSessionSafe = useCallback((s: Session | null) => {
    setSession((prev) => {
      if (!prev && !s) return null;
      if (prev && s && prev.token === s.token && prev.user.id === s.user.id) return prev;
      return s;
    });
  }, []);

  useEffect(() => {
    // Sync with other tabs if needed
    const handleStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) {
        try {
          const next = e.newValue ? JSON.parse(e.newValue) : null;
          setSessionSafe(next);
        } catch {
          return;
        }
      }
    };
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, [setSessionSafe]);

  const login = async (email: string, role: Role, password: string) => {
    const tokenRes = await loginAccessToken({ username: email, password });
    const name = email
      .split("@")[0]
      .replace(/[._-]/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());
    const u: User = {
      id: "u-" + Math.random().toString(36).slice(2, 8),
      name: name || (role === "admin" ? "Admin User" : "Staff User"),
      email,
      role,
    };
    const next: Session = { user: u, token: tokenRes.accessToken, tokenType: tokenRes.tokenType };
    setSessionSafe(next);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    }
  };

  const logout = () => {
    setSessionSafe(null);
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  };

  return (
    <AuthContext.Provider value={{ user, token, login, logout }}>{children}</AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

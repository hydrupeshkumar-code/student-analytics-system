import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { get, post, setUnauthorizedHandler, tokens } from "./api";
import type { User } from "./types";

interface TokenResponse { access_token: string; refresh_token: string; user: User }
interface AuthCtx {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  logout: () => void;
  setSession: (t: TokenResponse) => void;
  refreshUser: () => Promise<void>;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => { tokens.clear(); setUser(null); }, []);
  const setSession = useCallback((t: TokenResponse) => { tokens.set(t.access_token, t.refresh_token); setUser(t.user); }, []);
  const refreshUser = useCallback(async () => { setUser(await get<User>("/auth/me")); }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null));
    if (!tokens.access) { setLoading(false); return; }
    get<User>("/auth/me").then(setUser).catch(() => tokens.clear()).finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const t = await post<TokenResponse>("/auth/login", { email, password });
    setSession(t);
    return t.user;
  }, [setSession]);

  return <Ctx.Provider value={{ user, loading, login, logout, setSession, refreshUser }}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth outside AuthProvider");
  return c;
}

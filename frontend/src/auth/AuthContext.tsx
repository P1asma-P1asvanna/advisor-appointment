import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "../api/endpoints";
import { setUnauthorizedHandler, tokenStore } from "../api/client";
import type { Role, User } from "../api/types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login(email: string, password: string, role: Role): Promise<User>;
  logout(): void;
  /** Replace the session, e.g. with the fresh token returned after a password change. */
  setSession(token: string, user: User): void;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(!!tokenStore.get());

  const logout = useCallback(() => {
    tokenStore.set(null);
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout); // an expired token anywhere sends the user back to the login page
    if (!tokenStore.get()) return;
    api.me().then(setUser).catch(() => tokenStore.set(null)).finally(() => setLoading(false));
  }, [logout]);

  const login = useCallback(async (email: string, password: string, role: Role) => {
    const r = await api.login(email, password, role);
    tokenStore.set(r.access_token);
    setUser(r.user);
    return r.user;
  }, []);

  const setSession = useCallback((token: string, u: User) => {
    tokenStore.set(token);
    setUser(u);
  }, []);

  const value = useMemo(() => ({ user, loading, login, logout, setSession }), [user, loading, login, logout, setSession]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth outside AuthProvider");
  return v;
}

export const homeFor = (role: Role) => (role === "student" ? "/book" : role === "advisor" ? "/slots" : "/overview");

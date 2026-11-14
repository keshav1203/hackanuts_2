import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, setToken, getToken } from "@/lib/api";

export const DEMO = { email: "demo@scalepilot.ai", password: "demo1234" };

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  // Restore the session on page load.
  useEffect(() => {
    if (!getToken()) return setReady(true);
    api.me()
      .then((u) => setUser({ email: u.email }))
      .catch(() => setToken(null))
      .finally(() => setReady(true));
  }, []);

  // Any 401 (expired, or replaced by a newer login) signs this tab out.
  useEffect(() => {
    const out = () => { setToken(null); setUser(null); };
    window.addEventListener("sp:unauthorized", out);
    return () => window.removeEventListener("sp:unauthorized", out);
  }, []);

  // Notice quickly when the same email signs in elsewhere.
  useEffect(() => {
    if (!user) return;
    const id = setInterval(() => api.me().catch(() => {}), 20000);
    return () => clearInterval(id);
  }, [user]);

  const finish = useCallback((t) => { setToken(t.token); setUser({ email: t.email }); }, []);
  const signIn = useCallback(async (email, password) => finish(await api.login(email, password)), [finish]);
  const signUp = useCallback(async (email, password) => finish(await api.signup(email, password)), [finish]);
  const demoSignIn = useCallback(async () => finish(await api.demo()), [finish]);
  const signOut = useCallback(async () => {
    try { await api.logout(); } catch { /* already signed out */ }
    setToken(null);
    setUser(null);
  }, []);

  if (!ready) return null;
  return <AuthContext.Provider value={{ user, signUp, signIn, demoSignIn, signOut }}>{children}</AuthContext.Provider>;
}

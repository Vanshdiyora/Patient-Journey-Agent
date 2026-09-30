import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { authApi } from "../services";

const AuthContext = createContext(null);

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(localStorage.getItem("carepath_token"));
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem("carepath_user") || "null"); }
    catch { return null; }
  });
  const [booting, setBooting] = useState(Boolean(token));

  useEffect(() => {
    if (!token) return;
    authApi.me()
      .then(me => {
        setUser(me);
        localStorage.setItem("carepath_user", JSON.stringify(me));
      })
      .catch(() => {
        localStorage.removeItem("carepath_token");
        localStorage.removeItem("carepath_user");
        setToken(null);
        setUser(null);
      })
      .finally(() => setBooting(false));
  }, [token]);

  const login = async (credentials) => {
    const result = await authApi.login(credentials);
    const accessToken = result.access_token || result.token;
    if (!accessToken) throw new Error("Authentication response did not contain an access token.");
    localStorage.setItem("carepath_token", accessToken);
    setToken(accessToken);
    const me = result.user || await authApi.me();
    localStorage.setItem("carepath_user", JSON.stringify(me));
    setUser(me);
  };

  const logout = () => {
    localStorage.removeItem("carepath_token");
    localStorage.removeItem("carepath_user");
    setToken(null);
    setUser(null);
  };

  const value = useMemo(() => ({ token, user, login, logout }), [token, user]);
  if (booting) return <div className="app-loader"><div className="spinner" /><span>Loading CarePath…</span></div>;
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}


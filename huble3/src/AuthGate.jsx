import { useCallback, useEffect, useState } from "react";
import App from "./App.jsx";
import Login from "./Login.jsx";
import "./Auth.css";

const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

function readCookie(name) {
  const prefix = `${name}=`;
  const entry = document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith(prefix));
  return entry ? decodeURIComponent(entry.slice(prefix.length)) : "";
}

export default function AuthGate() {
  const [status, setStatus] = useState("checking");
  const [user, setUser] = useState(null);
  const [error, setError] = useState("");
  const [loggingOut, setLoggingOut] = useState(false);
  const [authError, setAuthError] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get("auth_error") || "";
  });

  useEffect(() => {
    // Remove ?auth_error=... from the address bar once it has been read.
    if (authError) window.history.replaceState({}, "", window.location.pathname);
  }, [authError]);

  const checkSession = useCallback(async () => {
    setStatus("checking");
    setError("");
    try {
      const response = await fetch(`${API_URL}/auth/me`, { credentials: "include" });
      if (response.status === 401) {
        setUser(null);
        setStatus("signed-out");
        return;
      }
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.authenticated || !data.user) {
        throw new Error(data.detail || "Unable to verify your session.");
      }
      setUser(data.user);
      setStatus("signed-in");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not connect to BuildAI backend.");
      setStatus("offline");
    }
  }, []);

  useEffect(() => { checkSession(); }, [checkSession]);

  async function handleLogout() {
    setLoggingOut(true);
    setError("");
    try {
      const csrfToken = readCookie("buildai_csrf");
      const response = await fetch(`${API_URL}/auth/logout`, {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRF-Token": csrfToken },
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Logout failed. Please try again.");
      }
      setUser(null);
      setStatus("signed-out");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Logout failed.");
    } finally {
      setLoggingOut(false);
    }
  }

  if (status === "checking") {
    return <div className="auth-loading"><div className="auth-orb">✳</div><div className="auth-loading-title">BuildAI</div><div className="auth-spinner" /><p>Checking your secure session…</p></div>;
  }

  if (status === "offline") {
    return <main className="auth-screen"><section className="auth-card auth-error-card"><div className="auth-orb">✳</div><p className="auth-eyebrow">CONNECTION REQUIRED</p><h1>Can’t reach BuildAI</h1><p className="auth-subtitle">The frontend couldn’t verify your session with the FastAPI backend.</p><div className="auth-alert">{error}</div><p className="auth-help">Make sure your backend is running at <code>{API_URL}</code>.</p><button className="auth-primary" onClick={checkSession}>Retry connection <span>↗</span></button></section></main>;
  }

  if (status === "signed-out") return <Login apiUrl={API_URL} error={authError} onDismiss={() => setAuthError("")} />;

  return <><div className="account-strip"><div className="account-identity"><span className="account-avatar">{user?.display_name?.trim()?.charAt(0)?.toUpperCase() || "U"}</span><span className="account-name">{user?.display_name || user?.email}</span><span className="account-dot" title="Signed in" /></div><button className="account-logout" onClick={handleLogout} disabled={loggingOut}>{loggingOut ? "Signing out…" : "Sign out ↗"}</button></div>{error && <div className="account-error" role="alert">{error}</div>}<App /></>;
}

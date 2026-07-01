import { API_BASE } from "./tokens";

const ACCESS_KEY = "dclaw_token";
const REFRESH_KEY = "dclaw_refresh";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACCESS_KEY);
}

function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(REFRESH_KEY);
}

function setTokens(access: string, refresh: string) {
  window.localStorage.setItem(ACCESS_KEY, access);
  window.localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearToken() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(ACCESS_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
}

async function authRequest(path: "login" | "register", email: string, password: string) {
  const res = await fetch(`${API_BASE}/api/v1/rag/auth/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Authentication failed (${res.status})`);
  }
  const data = await res.json();
  setTokens(data.access_token, data.refresh_token);
}

export const login = (email: string, password: string) => authRequest("login", email, password);
export const register = (email: string, password: string) =>
  authRequest("register", email, password);

/** Exchange the refresh token for a fresh access token. Returns success. */
export async function refreshAccessToken(): Promise<boolean> {
  const refresh_token = getRefreshToken();
  if (!refresh_token) return false;
  const res = await fetch(`${API_BASE}/api/v1/rag/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token }),
  });
  if (!res.ok) {
    clearToken();
    return false;
  }
  const data = await res.json();
  setTokens(data.access_token, data.refresh_token);
  return true;
}

export async function logout() {
  const refresh_token = getRefreshToken();
  if (refresh_token) {
    // best-effort server-side revocation
    await fetch(`${API_BASE}/api/v1/rag/auth/logout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token }),
    }).catch(() => {});
  }
  clearToken();
  if (typeof window !== "undefined") window.location.href = "/login";
}

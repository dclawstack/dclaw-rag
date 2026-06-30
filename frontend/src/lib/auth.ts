import { API_BASE } from "./tokens";

const TOKEN_KEY = "dclaw_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

function setToken(token: string) {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  if (typeof window !== "undefined") window.localStorage.removeItem(TOKEN_KEY);
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
  setToken(data.access_token);
}

export const login = (email: string, password: string) => authRequest("login", email, password);
export const register = (email: string, password: string) =>
  authRequest("register", email, password);

export function logout() {
  clearToken();
  if (typeof window !== "undefined") window.location.href = "/login";
}

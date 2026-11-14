const rawBase = import.meta.env.VITE_API_URL || "http://localhost:8000";
const BASE = rawBase.replace(/\/+$/, "");
const KEY = "sp_token";

export const getToken = () => localStorage.getItem(KEY);
export const setToken = (t) => (t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY));

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, { method = "GET", body } = {}) {
  let res;
  try {
    res = await fetch(`${BASE}/api${path}`, {
      method,
      headers: { "Content-Type": "application/json", ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("Can't reach the server. Check that the backend is running.", 0);
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 401 && getToken()) window.dispatchEvent(new Event("sp:unauthorized"));
    const detail = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join(", ") : data.detail;
    throw new ApiError(detail || "Something went wrong.", res.status);
  }
  return data;
}

export const api = {
  signup: (email, password) => request("/auth/signup", { method: "POST", body: { email, password } }),
  login: (email, password) => request("/auth/login", { method: "POST", body: { email, password } }),
  demo: () => request("/auth/demo", { method: "POST" }),
  me: () => request("/auth/me"),
  logout: () => request("/auth/logout", { method: "POST" }),
  createAnalysis: (repo_url, target_users, model) =>
    request("/analyses", { method: "POST", body: { repo_url, target_users, model } }),
  listAnalyses: () => request("/analyses"),
  getAnalysis: (id) => request(`/analyses/${id}`),
  runLoadTest: (id) => request(`/analyses/${id}/load-test`, { method: "POST" }),
  ask: (id, query, model) => request(`/analyses/${id}/ask`, { method: "POST", body: { query, model } }),
  checkHealth: () => request("/health"),
  checkGroqHealth: () => request("/health/groq"),
};

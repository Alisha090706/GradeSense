/**
 * Fetch wrapper — the single place that knows how to attach auth headers,
 * survive a 401 by refreshing once, and turn a non-2xx response into a
 * thrown Error with the backend's own detail message (every route in
 * Phases 1-10 returns {"detail": "..."} on error, via FastAPI's
 * HTTPException — see backend/app/api/v1/*.py).
 *
 * Tokens are stored in localStorage, not an httpOnly cookie — a real
 * tradeoff (XSS-exposed, but the backend's Phase 1 design returns tokens
 * in a JSON body rather than setting cookies, so this is the option that
 * matches what the API actually does today). Moving to httpOnly cookies
 * is real hardening worth doing later; it needs a backend change
 * (set-cookie on login/refresh) to go with it, not just a frontend one —
 * flagged here rather than silently accepted as final.
 */
const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

const TOKEN_KEY = "gradesense_access_token";
const REFRESH_KEY = "gradesense_refresh_token";

export function getAccessToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens({ access_token, refresh_token }) {
  localStorage.setItem(TOKEN_KEY, access_token);
  if (refresh_token) localStorage.setItem(REFRESH_KEY, refresh_token);
}

export function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

let refreshInFlight = null;

async function refreshAccessToken() {
  // Coalesce concurrent 401s into a single refresh call rather than firing one
  // per failed request — several components can hit a stale token at once.
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    const refreshToken = getRefreshToken();
    if (!refreshToken) throw new ApiError("Not authenticated", 401);

    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) {
      clearTokens();
      throw new ApiError("Session expired", 401);
    }
    const data = await res.json();
    setTokens(data);
    return data.access_token;
  })();

  try {
    return await refreshInFlight;
  } finally {
    refreshInFlight = null;
  }
}

/**
 * @param {string} path - e.g. "/courses" (relative to API_BASE)
 * @param {object} [options]
 * @param {boolean} [options.auth=true] - attach the Authorization header
 * @param {boolean} [options.isFormData=false] - skip JSON content-type/stringify (file uploads)
 */
export async function apiFetch(path, { method = "GET", body, auth = true, isFormData = false } = {}) {
  const headers = {};
  if (!isFormData) headers["Content-Type"] = "application/json";
  if (auth) {
    const token = getAccessToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const doFetch = () =>
    fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: isFormData ? body : body ? JSON.stringify(body) : undefined,
    });

  let res = await doFetch();

  if (res.status === 401 && auth && getRefreshToken()) {
    try {
      await refreshAccessToken();
      headers["Authorization"] = `Bearer ${getAccessToken()}`;
      res = await doFetch();
    } catch {
      // fall through — the retried request's own error handling below fires
    }
  }

  if (res.status === 204) return null;

  const isJson = res.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await res.json().catch(() => null) : await res.text();

  if (!res.ok) {
    const message = (isJson && data?.detail) || (typeof data === "string" && data) || `Request failed (${res.status})`;
    throw new ApiError(message, res.status);
  }
  return data;
}

export { ApiError };

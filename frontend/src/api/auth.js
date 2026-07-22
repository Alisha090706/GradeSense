import { apiFetch, clearTokens, setTokens } from "./client.js";

export async function registerStudent({ email, password, studentNumber }) {
  return apiFetch("/auth/register/student", {
    method: "POST",
    auth: false,
    body: { email, password, student_number: studentNumber || null },
  });
}

export async function registerTeacher({ email, password, institution }) {
  return apiFetch("/auth/register/teacher", {
    method: "POST",
    auth: false,
    body: { email, password, institution: institution || null },
  });
}

export async function verifyEmail(token) {
  return apiFetch(`/auth/verify-email?token=${encodeURIComponent(token)}`, { method: "POST", auth: false });
}

export async function login({ email, password }) {
  const data = await apiFetch("/auth/login", { method: "POST", auth: false, body: { email, password } });
  setTokens(data);
  return data;
}

export async function logout() {
  const { getRefreshToken } = await import("./client.js");
  const refreshToken = getRefreshToken();
  if (refreshToken) {
    await apiFetch("/auth/logout", { method: "POST", auth: false, body: { refresh_token: refreshToken } }).catch(() => {
      // logout is best-effort client-side regardless of whether the server call succeeds
    });
  }
  clearTokens();
}

export async function getMe() {
  return apiFetch("/users/me");
}

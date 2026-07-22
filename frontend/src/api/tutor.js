import { apiFetch } from "./client.js";

export async function askTutor({ question, submissionId }) {
  return apiFetch("/tutor/ask", { method: "POST", body: { question, submission_id: submissionId || null } });
}

export async function getTutorHistory(submissionId) {
  const query = submissionId ? `?submission_id=${encodeURIComponent(submissionId)}` : "";
  return apiFetch(`/tutor/history${query}`);
}

import { apiFetch } from "./client.js";

/**
 * @param {string} assignmentId
 * @param {{content: string, language?: string}} payload - language is ignored
 *   server-side for non-Programming assignment types (see backend
 *   submission_service.py's create_submission — a real fix from Phase 6,
 *   not something the frontend needs to work around).
 */
export async function submit(assignmentId, payload) {
  return apiFetch(`/assignments/${assignmentId}/submissions`, { method: "POST", body: payload });
}

export async function listMySubmissions(assignmentId) {
  return apiFetch(`/assignments/${assignmentId}/submissions/mine`);
}

export async function getSubmission(submissionId) {
  return apiFetch(`/submissions/${submissionId}`);
}

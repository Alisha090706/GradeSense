import { apiFetch } from "./client.js";

export async function listAssignments(courseId) {
  return apiFetch(`/courses/${courseId}/assignments`);
}

export async function getAssignment(assignmentId) {
  return apiFetch(`/assignments/${assignmentId}`);
}

export async function listTestCases(assignmentId) {
  return apiFetch(`/assignments/${assignmentId}/test-cases`);
}

import { apiFetch } from "./client.js";

export async function refreshCourseAnalytics(courseId) {
  return apiFetch(`/courses/${courseId}/analytics/refresh`, { method: "POST" });
}

export async function getCourseAnalytics(courseId) {
  return apiFetch(`/courses/${courseId}/analytics`);
}

export async function refreshAssignmentAnalytics(assignmentId) {
  return apiFetch(`/assignments/${assignmentId}/analytics/refresh`, { method: "POST" });
}

export async function getAssignmentAnalytics(assignmentId) {
  return apiFetch(`/assignments/${assignmentId}/analytics`);
}

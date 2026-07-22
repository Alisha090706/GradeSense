import { apiFetch } from "./client.js";

export async function listCourses() {
  return apiFetch("/courses");
}

export async function getCourse(courseId) {
  return apiFetch(`/courses/${courseId}`);
}

export async function listSubjects() {
  return apiFetch("/subjects");
}

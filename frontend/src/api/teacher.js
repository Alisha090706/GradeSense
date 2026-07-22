import { apiFetch } from "./client.js";

export async function createCourse({ name, subjectId }) {
  return apiFetch("/courses", { method: "POST", body: { name, subject_id: subjectId } });
}

export async function listAssignmentTemplates() {
  return apiFetch("/assignment-templates");
}

export async function createAssignment(courseId, payload) {
  return apiFetch(`/courses/${courseId}/assignments`, { method: "POST", body: payload });
}

export async function updateAssignment(assignmentId, payload) {
  return apiFetch(`/assignments/${assignmentId}`, { method: "PATCH", body: payload });
}

export async function addTestCase(assignmentId, payload) {
  return apiFetch(`/assignments/${assignmentId}/test-cases`, { method: "POST", body: payload });
}

export async function generateTestCases(assignmentId, { referenceSolution, functions, language = "python" }) {
  return apiFetch(`/assignments/${assignmentId}/test-cases/generate`, {
    method: "POST",
    body: { reference_solution: referenceSolution, functions, language },
  });
}

export async function regenerateRubric(assignmentId) {
  return apiFetch(`/assignments/${assignmentId}/rubric/generate`, { method: "POST" });
}

export async function uploadDocument(courseId, file) {
  const formData = new FormData();
  formData.append("file", file);
  return apiFetch(`/courses/${courseId}/documents`, { method: "POST", body: formData, isFormData: true });
}

export async function listDocuments(courseId) {
  return apiFetch(`/courses/${courseId}/documents`);
}

export async function deleteDocument(documentId) {
  return apiFetch(`/documents/${documentId}`, { method: "DELETE" });
}

import { apiFetch } from "./client.js";

export async function listVerificationRequests(statusFilter = "pending") {
  return apiFetch(`/admin/verification-requests?status_filter=${encodeURIComponent(statusFilter)}`);
}

export async function approveVerificationRequest(requestId) {
  return apiFetch(`/admin/verification-requests/${requestId}/approve`, { method: "POST", body: {} });
}

export async function rejectVerificationRequest(requestId) {
  return apiFetch(`/admin/verification-requests/${requestId}/reject`, { method: "POST", body: {} });
}

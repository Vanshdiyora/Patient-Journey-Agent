/** Resource clients share the transport in client.js and the /api/v1 contract. */

import api, { get, post, patch } from "./client";

/** Login, signup and identity endpoints. */
export const authApi = {
  login: (payload) => post("/api/v1/auth/login", payload),
  signup: (payload) => post("/api/v1/auth/signup", payload),
  me: () => get("/api/v1/users/me"),
};

/** Staff dashboard summary (role-scoped server-side). */
export const dashboardApi = {
  summary: () => get("/api/v1/dashboard/summary"),
};

/** Lightweight liveness probe used by the dashboard System pulse panel. */
export const healthApi = {
  check: () => get("/api/v1/health"),
};

/** Patient directory (staff only, scoped server-side). */
export const patientsApi = {
  list: (params) => get("/api/v1/patients", params),
  get: (id) => get(`/api/v1/patients/${id}`),
  journeys: (id, params) => get(`/api/v1/patients/${id}/journeys`, params),
  startJourney: (id, payload) => post(`/api/v1/patients/${id}/journeys`, payload),
};

/**
 * Journey operations (staff only). Identity/scope come from the bearer token
 * server-side; the UI never sends ownership data.
 */
export const journeysApi = {
  list: (params) => get("/api/v1/journeys", params),
  availablePathways: () => get("/api/v1/journeys/available-pathways"),
  get: (id) => get(`/api/v1/journeys/${id}`),
  steps: (id) => get(`/api/v1/journeys/${id}/steps`),
  completeStep: (journeyId, stepId) =>
    post(`/api/v1/journeys/${journeyId}/steps/${stepId}/complete`, { confirmed: true }),
  addStepEvidence: (journeyId, stepId, details, file, evidenceType = "RESULT", approvalConfirmed = false) => {
    const form = new FormData();
    form.append("details", details);
    form.append("evidence_type", evidenceType);
    form.append("approval_confirmed", String(approvalConfirmed));
    if (file) form.append("file", file);
    return api.post(`/api/v1/journeys/${journeyId}/steps/${stepId}/evidence`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    })
      .then(response => response.data);
  },
  downloadStepEvidence: async (journeyId, stepId, fileId, fileName) => {
    const response = await api.get(
      `/api/v1/journeys/${journeyId}/steps/${stepId}/evidence/${fileId}`,
      { responseType: "blob" },
    );
    const url = URL.createObjectURL(response.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName || "evidence";
    link.click();
    URL.revokeObjectURL(url);
  },
  updateStepTimeLimit: (journeyId, stepId, time_limit_hours) =>
    patch(`/api/v1/journeys/${journeyId}/steps/${stepId}/time-limit`, { time_limit_hours }),
  evaluate: (id) => post(`/api/v1/journeys/${id}/evaluate`),
  orchestrate: (id) => post(`/api/v1/journeys/${id}/orchestrate`),
  events: (id, params) => get(`/api/v1/journeys/${id}/events`, params),
  addEvent: (id, payload) => post(`/api/v1/journeys/${id}/events`, payload),
  actions: (id, params) => get(`/api/v1/journeys/${id}/actions`, params),
  approveAction: (actionId) => post(`/api/v1/actions/${actionId}/approve`),
  rejectAction: (actionId, note) => post(`/api/v1/actions/${actionId}/reject`, { note }),
};

/** Exception queue (staff only; resolve via PATCH). */
export const exceptionsApi = {
  list: (params) => get("/api/v1/exceptions", params),
  update: (id, payload) => patch(`/api/v1/exceptions/${id}`, payload),
};

/** Agent run audit feed (observability; staff only). */
export const agentsApi = {
  runs: (params) => get("/api/v1/agent-runs", params),
};

/**
 * Admin-only user management. The backend enforces require_admin; this module
 * exists so UserManagement has a dedicated, auditable client.
 */
export const adminApi = {
  users: (params) => get("/api/v1/admin/users", params),
  createStaff: (payload) => post("/api/v1/admin/users", payload),
  patientAssignments: (id) => get(`/api/v1/admin/users/${id}/patients`),
  assignPatient: (id, patientId) => api.put(`/api/v1/admin/users/${id}/patients/${patientId}`).then(r => r.data),
  unassignPatient: (id, patientId) => api.delete(`/api/v1/admin/users/${id}/patients/${patientId}`).then(r => r.data),
  setUserRole: (id, payload) => patch(`/api/v1/admin/users/${id}/role`, payload),
  setUserActive: (id, payload) => patch(`/api/v1/admin/users/${id}/status`, payload),
};

/**
 * Patient-scoped APIs (/api/v1/me...): identity comes from the token
 * server-side; the UI never sends patient/journey ownership data.
 */
export const meApi = {
  profile: () => get("/api/v1/me"),
  journeys: (params) => get("/api/v1/me/journeys", params),
  journey: (id) => get(`/api/v1/me/journeys/${id}`),
  journeySteps: (id) => get(`/api/v1/me/journeys/${id}/steps`),
  journeyEvents: (id, params) => get(`/api/v1/me/journeys/${id}/events`, params),
  submitEvent: (id, payload) => post(`/api/v1/me/journeys/${id}/events`, payload),
  submitStep: (journeyId, stepId, comment) =>
    post(`/api/v1/me/journeys/${journeyId}/steps/${stepId}/submit`, { comment }),
};

/** Administrator-managed care pathway templates. */
export const pathwaysApi = {
  list: (params) => get("/api/v1/pathways", params),
  create: (payload) => post("/api/v1/pathways", payload),
  update: (id, payload) => api.put(`/api/v1/pathways/${id}`, payload).then(response => response.data),
};

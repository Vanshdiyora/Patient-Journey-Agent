import api, { get, patch, post } from "../../../services/client";

export const adminApi = {
  users: (params) => get("/api/v1/admin/users", params),
  clinicians: () => get("/api/v1/admin/clinicians"),
  createPatient: (payload) => post("/api/v1/admin/patients", payload),
  createStaff: (payload) => post("/api/v1/admin/users", payload),
  patientAssignments: (id) => get(`/api/v1/admin/users/${id}/patients`),
  assignPatient: (id, patientId) => api.put(`/api/v1/admin/users/${id}/patients/${patientId}`).then(r => r.data),
  unassignPatient: (id, patientId) => api.delete(`/api/v1/admin/users/${id}/patients/${patientId}`).then(r => r.data),
  setUserRole: (id, payload) => patch(`/api/v1/admin/users/${id}/role`, payload),
  setUserActive: (id, payload) => patch(`/api/v1/admin/users/${id}/status`, payload),
};

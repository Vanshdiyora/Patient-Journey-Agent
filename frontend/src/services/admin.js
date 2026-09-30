import { get, patch } from "./client";

/**
 * Admin-only user management. The backend enforces require_admin; this module
 * exists so UserManagement has a dedicated, auditable client.
 */
export const adminApi = {
  users: (params) => get("/api/v1/admin/users", params),
  setUserRole: (id, payload) => patch(`/api/v1/admin/users/${id}/role`, payload),
  setUserActive: (id, payload) => patch(`/api/v1/admin/users/${id}/status`, payload),
};

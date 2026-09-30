import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
  headers: { "Content-Type": "application/json" },
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("carepath_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("carepath_token");
      localStorage.removeItem("carepath_user");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    // 403s are surfaced to pages via getErrorMessage; no global redirect so a
    // stale link shows an access-denied state instead of bouncing the user.
    return Promise.reject(error);
  }
);

const get = (url, params) => api.get(url, { params }).then(r => r.data);
const post = (url, data) => api.post(url, data).then(r => r.data);
const patch = (url, data) => api.patch(url, data).then(r => r.data);

export const authApi = {
  login: (payload) => post("/api/v1/auth/login", payload),
  me: () => get("/api/v1/users/me"),
};

export const dashboardApi = {
  summary: () => get("/api/v1/dashboard/summary"),
};

export const patientsApi = {
  list: (params) => get("/api/v1/patients", params),
  get: (id) => get(`/api/v1/patients/${id}`),
  journeys: (id) => get(`/api/v1/patients/${id}/journeys`),
};

export const journeysApi = {
  list: (params) => get("/api/v1/journeys", params),
  get: (id) => get(`/api/v1/journeys/${id}`),
  steps: (id) => get(`/api/v1/journeys/${id}/steps`),
  evaluate: (id) => post(`/api/v1/journeys/${id}/evaluate`),
  context: (id) => get(`/api/v1/journeys/${id}/orchestration-context`),
  orchestrate: (id) => post(`/api/v1/journeys/${id}/orchestrate`),
  events: (id, params) => get(`/api/v1/journeys/${id}/events`, params),
  addEvent: (id, payload) => post(`/api/v1/journeys/${id}/events`, payload),
  actions: (id) => get(`/api/v1/journeys/${id}/actions`),
};

export const exceptionsApi = {
  list: (params) => get("/api/v1/exceptions", params),
  update: (id, payload) => patch(`/api/v1/exceptions/${id}`, payload),
};

export const agentsApi = {
  runs: (params) => get("/api/v1/agent-runs", params),
};

export const actionsApi = {
  registry: () => get("/api/v1/actions/registry"),
};

export const healthApi = {
  check: () => get("/api/v1/health"),
};

// Admin-only user management (backend enforces require_admin).
export const adminApi = {
  users: (params) => get("/api/v1/admin/users", params),
  setUserRole: (id, payload) => patch(`/api/v1/admin/users/${id}/role`, payload),
  setUserActive: (id, payload) => patch(`/api/v1/admin/users/${id}/status`, payload),
};

// Patient-scoped APIs: identity comes from the token server-side; the UI never
// sends patient/journey ownership data.
export const meApi = {
  profile: () => get("/api/v1/me"),
  journeys: () => get("/api/v1/me/journeys"),
  journey: (id) => get(`/api/v1/me/journeys/${id}`),
  journeySteps: (id) => get(`/api/v1/me/journeys/${id}/steps`),
  journeyEvents: (id) => get(`/api/v1/me/journeys/${id}/events`),
  submitEvent: (id, payload) => post(`/api/v1/me/journeys/${id}/events`, payload),
};

export default api;

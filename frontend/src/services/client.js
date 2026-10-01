import axios from "axios";

/**
 * The single axios instance for the app. Resource modules (auth.js,
 * patients.js, ...) import `api` from here and never build their own clients,
 * so interceptors (token attach, 401 logout, error shape) stay consistent.
 */
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
  headers: { "Content-Type": "application/json" },
  timeout: 600000,
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

/** GET returning `data` (unwraps the axios response). */
export const get = (url, params) => api.get(url, { params }).then(r => r.data);
/** POST returning `data`. */
export const post = (url, data) => api.post(url, data).then(r => r.data);
/** PATCH returning `data`. */
export const patch = (url, data) => api.patch(url, data).then(r => r.data);

export default api;

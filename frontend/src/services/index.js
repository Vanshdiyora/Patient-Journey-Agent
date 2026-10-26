/** Public service API for application screens and shared UI. */
export { default as api } from "./client";
export { chatApi } from "./chat";
export { notificationsApi } from "../features/notifications/services/api";
export {
  authApi, dashboardApi, healthApi, patientsApi, journeysApi,
  exceptionsApi, agentsApi, adminApi, meApi, pathwaysApi,
} from "./api";

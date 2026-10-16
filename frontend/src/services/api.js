/**
 * Compatibility barrel for resource API clients. Feature implementations live
 * in their owning feature's services folder and share the client transport.
 */
export { authApi } from "../features/authentication/services/api";
export { dashboardApi, healthApi } from "../features/dashboard/services/api";
export { patientsApi } from "../features/patients/services/api";
export { journeysApi } from "../features/journeys/services/api";
export { exceptionsApi } from "../features/exceptions/services/api";
export { agentsApi } from "../features/agent-runs/services/api";
export { adminApi } from "../features/administration/services/api";
export { meApi } from "../features/patient-portal/services/api";
export { pathwaysApi } from "../features/pathways/services/api";

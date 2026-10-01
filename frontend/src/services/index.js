/**
 * Barrel for the API layer. Feature code imports from "services" — e.g.
 * `import { patientsApi } from "../services"` — so the transport details stay
 * swappable behind one module boundary.
 */
export { default as api } from "./client";
export { authApi } from "./auth";
export { chatApi } from "./chat";
export { dashboardApi, healthApi } from "./dashboard";
export { patientsApi } from "./patients";
export { journeysApi } from "./journeys";
export { exceptionsApi } from "./exceptions";
export { agentsApi } from "./agents";
export { actionsApi } from "./actions";
export { adminApi } from "./admin";
export { meApi } from "./me";

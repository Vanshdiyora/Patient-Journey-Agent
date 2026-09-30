import { get } from "./client";

/** Staff dashboard summary (role-scoped server-side). */
export const dashboardApi = {
  summary: () => get("/api/v1/dashboard/summary"),
};

/** Lightweight liveness probe used by the dashboard System pulse panel. */
export const healthApi = {
  check: () => get("/api/v1/health"),
};

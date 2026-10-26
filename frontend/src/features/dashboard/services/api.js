import { get } from "../../../services/client";

export const dashboardApi = {
  summary: () => get("/api/v1/dashboard/summary"),
};

export const healthApi = {
  check: () => get("/api/v1/health"),
};

import { get } from "./client";

/** Agent run audit feed (observability; staff only). */
export const agentsApi = {
  runs: (params) => get("/api/v1/agent-runs", params),
};

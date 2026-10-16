import { get } from "../../../services/client";

export const agentsApi = {
  runs: (params) => get("/api/v1/agent-runs", params),
};

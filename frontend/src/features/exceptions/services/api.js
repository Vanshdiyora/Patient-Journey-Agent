import { get, patch } from "../../../services/client";

export const exceptionsApi = {
  list: (params) => get("/api/v1/exceptions", params),
  update: (id, payload) => patch(`/api/v1/exceptions/${id}`, payload),
};

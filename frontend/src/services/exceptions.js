import { get, patch } from "./client";

/** Exception queue (staff only; resolve via PATCH). */
export const exceptionsApi = {
  list: (params) => get("/api/v1/exceptions", params),
  update: (id, payload) => patch(`/api/v1/exceptions/${id}`, payload),
};

import { get, post } from "./client";
import api from "./client";

/** Administrator-managed care pathway templates. */
export const pathwaysApi = {
  list: () => get("/api/v1/pathways"),
  create: (payload) => post("/api/v1/pathways", payload),
  update: (id, payload) => api.put(`/api/v1/pathways/${id}`, payload).then(response => response.data),
};

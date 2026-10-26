import api, { get, post } from "../../../services/client";

export const pathwaysApi = {
  list: (params) => get("/api/v1/pathways", params),
  create: (payload) => post("/api/v1/pathways", payload),
  update: (id, payload) => api.put(`/api/v1/pathways/${id}`, payload).then(response => response.data),
};

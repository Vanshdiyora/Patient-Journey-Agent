import { get, post } from "./client";

/** Patient directory (staff only, scoped server-side). */
export const patientsApi = {
  list: (params) => get("/api/v1/patients", params),
  get: (id) => get(`/api/v1/patients/${id}`),
  journeys: (id, params) => get(`/api/v1/patients/${id}/journeys`, params),
  startJourney: (id, payload) => post(`/api/v1/patients/${id}/journeys`, payload),
};

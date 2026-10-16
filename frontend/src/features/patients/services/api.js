import { get, post } from "../../../services/client";

export const patientsApi = {
  list: (params) => get("/api/v1/patients", params),
  claim: (id) => post(`/api/v1/patients/${id}/claim`),
  get: (id) => get(`/api/v1/patients/${id}`),
  journeys: (id, params) => get(`/api/v1/patients/${id}/journeys`, params),
  startJourney: (id, payload) => post(`/api/v1/patients/${id}/journeys`, payload),
};

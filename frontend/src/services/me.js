import { get, post } from "./client";

/**
 * Patient-scoped APIs (/api/v1/me...): identity comes from the token
 * server-side; the UI never sends patient/journey ownership data.
 */
export const meApi = {
  profile: () => get("/api/v1/me"),
  journeys: () => get("/api/v1/me/journeys"),
  journey: (id) => get(`/api/v1/me/journeys/${id}`),
  journeySteps: (id) => get(`/api/v1/me/journeys/${id}/steps`),
  journeyEvents: (id) => get(`/api/v1/me/journeys/${id}/events`),
  submitEvent: (id, payload) => post(`/api/v1/me/journeys/${id}/events`, payload),
};

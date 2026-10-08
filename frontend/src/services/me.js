import { get, post } from "./client";

/**
 * Patient-scoped APIs (/api/v1/me...): identity comes from the token
 * server-side; the UI never sends patient/journey ownership data.
 */
export const meApi = {
  profile: () => get("/api/v1/me"),
  journeys: (params) => get("/api/v1/me/journeys", params),
  journey: (id) => get(`/api/v1/me/journeys/${id}`),
  journeySteps: (id) => get(`/api/v1/me/journeys/${id}/steps`),
  journeyEvents: (id, params) => get(`/api/v1/me/journeys/${id}/events`, params),
  submitEvent: (id, payload) => post(`/api/v1/me/journeys/${id}/events`, payload),
  submitStep: (journeyId, stepId, comment) =>
    post(`/api/v1/me/journeys/${journeyId}/steps/${stepId}/submit`, { comment }),
};

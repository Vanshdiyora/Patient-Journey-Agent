import { get, patch, post } from "./client";

/**
 * Journey operations (staff only). Identity/scope come from the bearer token
 * server-side; the UI never sends ownership data.
 */
export const journeysApi = {
  list: (params) => get("/api/v1/journeys", params),
  availablePathways: () => get("/api/v1/journeys/available-pathways"),
  get: (id) => get(`/api/v1/journeys/${id}`),
  steps: (id) => get(`/api/v1/journeys/${id}/steps`),
  completeStep: (journeyId, stepId) =>
    post(`/api/v1/journeys/${journeyId}/steps/${stepId}/complete`, { confirmed: true }),
  updateStepTimeLimit: (journeyId, stepId, time_limit_hours) =>
    patch(`/api/v1/journeys/${journeyId}/steps/${stepId}/time-limit`, { time_limit_hours }),
  evaluate: (id) => post(`/api/v1/journeys/${id}/evaluate`),
  context: (id) => get(`/api/v1/journeys/${id}/orchestration-context`),
  orchestrate: (id) => post(`/api/v1/journeys/${id}/orchestrate`),
  events: (id, params) => get(`/api/v1/journeys/${id}/events`, params),
  addEvent: (id, payload) => post(`/api/v1/journeys/${id}/events`, payload),
  actions: (id) => get(`/api/v1/journeys/${id}/actions`),
};

import api, { get, patch, post } from "../../../services/client";

export const journeysApi = {
  list: (params) => get("/api/v1/journeys", params),
  availablePathways: () => get("/api/v1/journeys/available-pathways"),
  get: (id) => get(`/api/v1/journeys/${id}`),
  updatePriority: (id, priority) => patch(`/api/v1/journeys/${id}/priority`, { priority }),
  steps: (id) => get(`/api/v1/journeys/${id}/steps`),
  completeStep: (journeyId, stepId) =>
    post(`/api/v1/journeys/${journeyId}/steps/${stepId}/complete`, { confirmed: true }),
  addStepEvidence: (journeyId, stepId, details, file, evidenceType = "RESULT", approvalConfirmed = false) => {
    const form = new FormData();
    form.append("details", details);
    form.append("evidence_type", evidenceType);
    form.append("approval_confirmed", String(approvalConfirmed));
    if (file) form.append("file", file);
    return api.post(`/api/v1/journeys/${journeyId}/steps/${stepId}/evidence`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    })
      .then(response => response.data);
  },
  downloadStepEvidence: async (journeyId, stepId, fileId, fileName) => {
    const response = await api.get(
      `/api/v1/journeys/${journeyId}/steps/${stepId}/evidence/${fileId}`,
      { responseType: "blob" },
    );
    const url = URL.createObjectURL(response.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName || "evidence";
    link.click();
    URL.revokeObjectURL(url);
  },
  updateStepTimeLimit: (journeyId, stepId, time_limit_hours) =>
    patch(`/api/v1/journeys/${journeyId}/steps/${stepId}/time-limit`, { time_limit_hours }),
  evaluate: (id) => post(`/api/v1/journeys/${id}/evaluate`),
  // The backend completes this request only after the orchestration run finishes.
  // It can take longer than the timeout used for ordinary API calls.
  orchestrate: (id) => api.post(`/api/v1/journeys/${id}/orchestrate`, null, { timeout: 0 }).then(response => response.data),
  events: (id, params) => get(`/api/v1/journeys/${id}/events`, params),
  addEvent: (id, payload) => post(`/api/v1/journeys/${id}/events`, payload),
  actions: (id, params) => get(`/api/v1/journeys/${id}/actions`, params),
  approveAction: (actionId) => post(`/api/v1/actions/${actionId}/approve`),
  rejectAction: (actionId, note) => post(`/api/v1/actions/${actionId}/reject`, { note }),
};

import api, { get, post, patch } from "./client";

/**
 * Assistant chat APIs. Sessions/messages are always scoped to the signed-in
 * user server-side. WebSocket transport connects to /ws/chat with the JWT as
 * a query param (browsers cannot set headers on WebSocket).
 */

export const chatApi = {
  createSession: (title) => post("/api/v1/chat/sessions", title ? { title } : {}),
  listSessions: (params) => get("/api/v1/chat/sessions", params),
  messages: (sessionId, params) => get(`/api/v1/chat/sessions/${sessionId}/messages`, params),
  renameSession: (sessionId, title) => patch(`/api/v1/chat/sessions/${sessionId}`, { title }),
  archiveSession: (sessionId) => api.delete(`/api/v1/chat/sessions/${sessionId}`).then(r => r.data),
};

/**
 * Open the chat WebSocket. The browser API cannot set an Authorization header,
 * so the existing JWT is passed in the handshake URL.
 */
export function openChatSocket(token) {
  const base = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000")
    .replace(/^http/, "ws").replace(/\/$/, "");
  return new WebSocket(`${base}/ws/chat?token=${encodeURIComponent(token || "")}`);
}

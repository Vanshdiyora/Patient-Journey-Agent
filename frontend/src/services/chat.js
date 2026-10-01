import api, { get, post, patch } from "./client";

/**
 * Assistant chat APIs. Sessions/messages are always scoped to the signed-in
 * user server-side. WebSocket transport connects to /ws/chat with the JWT as
 * a query param (browsers cannot set headers on WebSocket).
 */

export const chatApi = {
  createSession: (title) => post("/api/v1/chat/sessions", title ? { title } : {}),
  listSessions: () => get("/api/v1/chat/sessions"),
  messages: (sessionId) => get(`/api/v1/chat/sessions/${sessionId}/messages`),
  sendMessage: (sessionId, content) => post(`/api/v1/chat/sessions/${sessionId}/messages`, { content }),
  confirmAction: (sessionId, messageId) =>
    post(`/api/v1/chat/sessions/${sessionId}/messages/${messageId}/confirm`, {}),
  rejectAction: (sessionId, messageId) =>
    post(`/api/v1/chat/sessions/${sessionId}/messages/${messageId}/reject`, {}),
  renameSession: (sessionId, title) => patch(`/api/v1/chat/sessions/${sessionId}`, { title }),
  archiveSession: (sessionId) => api.delete(`/api/v1/chat/sessions/${sessionId}`).then(r => r.data),
};

/**
 * Open the chat WebSocket. Returns the socket instance; callers attach
 * onmessage/onclose. Keeps the JWT out of the URL beyond the handshake.
 */
export function openChatSocket({ onEvent, onClose }) {
  const token = localStorage.getItem("carepath_token") || "";
  const base = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000")
    .replace(/^http/, "ws");
  const socket = new WebSocket(`${base}/ws/chat?token=${encodeURIComponent(token)}`);
  if (onEvent) socket.onmessage = (e) => {
    try { onEvent(JSON.parse(e.data)); } catch { /* ignore malformed frames */ }
  };
  if (onClose) socket.onclose = onClose;
  return socket;
}

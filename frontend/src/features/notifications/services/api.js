import { get, patch } from "../../../services/client";

export const notificationsApi = {
  list: (params) => get("/api/v1/notifications", params),
  markRead: (id) => patch(`/api/v1/notifications/${id}/read`, {}),
};

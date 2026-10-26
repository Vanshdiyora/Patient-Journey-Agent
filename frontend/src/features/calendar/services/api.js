import { get, patch, post } from "../../../services/client";

export const calendarApi = {
  async events(params) {
    // A busy month can exceed one API page. Never silently drop later events.
    const first = await get("/api/v1/calendar/events", { ...params, limit: 1000, offset: 0 });
    const items = [...first.items];
    for (let offset = first.limit; offset < first.total; offset += first.limit) {
      const page = await get("/api/v1/calendar/events", { ...params, limit: first.limit, offset });
      items.push(...page.items);
    }
    return { ...first, items };
  },
  event: id => get(`/api/v1/calendar/events/${id}`),
  options: patientId => get("/api/v1/calendar/options", patientId ? { patient_id: patientId } : undefined),
  create: payload => post("/api/v1/calendar/events", payload),
  update: (id, payload) => patch(`/api/v1/calendar/events/${id}`, payload),
  cancel: (id, payload) => post(`/api/v1/calendar/events/${id}/cancel`, payload),
};

/**
 * Normalizers for backend list envelopes and badge CSS class builders.
 */

/** CSS class map for journey/step/exception status pills. */
export const STATUS_STYLES = {
  active: "status status--active",
  in_progress: "status status--active",
  completed: "status status--completed",
  resolved: "status status--completed",
  pending: "status status--pending",
  blocked: "status status--danger",
  open: "status status--danger",
  failed: "status status--danger",
  cancelled: "status status--muted",
  skipped: "status status--muted",
};

export function statusClass(value) {
  return STATUS_STYLES[String(value || "").toLowerCase()] || "status status--neutral";
}

export function priorityClass(value) {
  return `priority priority--${String(value || "normal").toLowerCase()}`;
}

export function severityClass(value) {
  return `severity severity--${String(value || "medium").toLowerCase()}`;
}

/**
 * Backend list endpoints return either a bare array or an envelope
 * ({ items } | { patients } | { journeys } | { runs } | { actions } | { registry }).
 * Normalize any of those shapes to a plain array.
 */
export function toList(data, ...keys) {
  if (Array.isArray(data)) return data;
  if (!data || typeof data !== "object") return [];
  for (const key of keys.length ? keys : ["items"]) {
    if (Array.isArray(data[key])) return data[key];
  }
  return [];
}

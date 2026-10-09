/** Shared formatting and API response helpers. */


/**
 * Date / duration formatting helpers.
 */

export function formatDate(value, withTime = false) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  });
}

export function formatDuration(start, end) {
  const ms = new Date(end) - new Date(start);
  if (!Number.isFinite(ms)) return "—";
  const s = Math.max(0, Math.round(ms / 1000));
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;
}

/**
 * Small text helpers.
 */

export function humanize(value) {
  return String(value || "—").replaceAll("_", " ").replace(/\b\w/g, c => c.toUpperCase());
}

export function initials(first = "", last = "") {
  return `${first?.[0] || ""}${last?.[0] || ""}`.toUpperCase() || "P";
}

export function shortId(id, length = 8) {
  if (id === undefined || id === null) return "—";
  return `#${String(id).slice(0, length)}`;
}

/**
 * API error extraction. Central so every surface reports failures identically.
 */

export function getErrorMessage(error) {
  const detail = error?.response?.data?.detail;

  if (typeof detail === "string") return detail;

  // FastAPI/Pydantic validation errors return an array of objects. Turn each
  // entry into readable text so React components never try to render objects.
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "string") return item;
        const location = Array.isArray(item?.loc) ? item.loc.filter((part) => part !== "body").join(" → ") : "";
        const message = item?.msg || "Invalid value";
        return location ? `${location}: ${message}` : message;
      })
      .join("; ");
  }

  if (detail && typeof detail === "object") {
    return detail.msg || detail.message || "The request was invalid.";
  }

  return error?.message || "Something went wrong.";
}

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
  wait: "status status--pending",
  escalate: "status status--danger",
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

export * from "./roles";

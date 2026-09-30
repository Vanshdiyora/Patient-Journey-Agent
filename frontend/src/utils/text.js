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

// Local wall-clock dates are converted to UTC only at the API boundary. Using
// calendar arithmetic preserves midnight and day lengths through DST changes.
export function dateKey(value) {
  const d = new Date(value);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function localInput(value) {
  if (!value) return "";
  const d = new Date(value);
  return `${dateKey(d)}T${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export function addDays(value, count) {
  const d = new Date(value);
  d.setDate(d.getDate() + count);
  return d;
}

export function viewRange(anchor, view) {
  let start = new Date(`${anchor}T00:00:00`);
  if (view === "month") {
    start.setDate(1);
    start = addDays(start, -(start.getDay() + 6) % 7);
    const monthEnd = new Date(`${anchor}T00:00:00`);
    monthEnd.setMonth(monthEnd.getMonth() + 1, 0);
    const end = addDays(monthEnd, 7 - ((monthEnd.getDay() + 6) % 7));
    return { start, end };
  }
  if (view === "week") start = addDays(start, -((start.getDay() + 6) % 7));
  return { start, end: addDays(start, view === "week" ? 7 : 1) };
}

export function rangeDays(start, end) {
  const days = [];
  for (let day = new Date(start); day < end; day = addDays(day, 1)) days.push(day);
  return days;
}

export function moveAnchor(anchor, view, direction) {
  const d = new Date(`${anchor}T00:00:00`);
  if (view === "month") {
    d.setDate(1);
    d.setMonth(d.getMonth() + direction);
  } else d.setDate(d.getDate() + direction * (view === "week" ? 7 : 1));
  return dateKey(d);
}

export function eventsForDay(events, day) {
  const start = new Date(`${dateKey(day)}T00:00:00`);
  const end = addDays(start, 1);
  return events.filter(event => event.all_day
    ? event.starts_at && dateKey(event.starts_at) === dateKey(day)
    : new Date(event.starts_at) < end && new Date(event.ends_at) > start);
}

export function timeLabel(event) {
  return event.all_day ? (event.date_source === "DEADLINE" ? "Due" : "Planned")
    : new Date(event.starts_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export const STATUS_LABELS = { UPCOMING: "Upcoming", COMPLETED: "Completed", OVERDUE: "Overdue", RESCHEDULED: "Rescheduled", CANCELLED: "Cancelled" };

export function preferredUnit(hours) {
  const value = Number(hours);
  if (value >= 168 && value % 168 === 0) return "weeks";
  if (value >= 24 && value % 24 === 0) return "days";
  return "hours";
}

export function formatDurationHours(hours) {
  if (hours == null || hours === "") return "Not set";
  const value = Number(hours);
  if (!Number.isInteger(value) || value < 0) return "Not set";
  if (value === 0) return "0 hours";
  const weeks = Math.floor(value / 168);
  const days = Math.floor((value % 168) / 24);
  const remainingHours = value % 24;
  return [
    weeks && `${weeks} ${weeks === 1 ? "week" : "weeks"}`,
    days && `${days} ${days === 1 ? "day" : "days"}`,
    remainingHours && `${remainingHours} ${remainingHours === 1 ? "hour" : "hours"}`,
  ].filter(Boolean).join(" ");
}

export function milestoneLabel(day) {
  if (day == null) return "Timing to be confirmed";
  if (Number(day) === 0) return "At the start";
  if (Number(day) >= 7 && Number(day) % 7 === 0) return `Week ${Number(day) / 7}`;
  return `Day ${day}`;
}

export function preferredUnit(hours) {
  const value = Number(hours);
  if (value >= 168 && value % 168 === 0) return "weeks";
  if (value >= 24 && value % 24 === 0) return "days";
  return "hours";
}

export function splitDurationHours(hours) {
  const value = Number(hours);
  if (!Number.isInteger(value) || value < 0) return null;
  return {
    weeks: Math.floor(value / 168),
    days: Math.floor((value % 168) / 24),
    hours: value % 24,
  };
}

export function durationHoursFromParts({ weeks = 0, days = 0, hours = 0 }) {
  return Number(weeks) * 168 + Number(days) * 24 + Number(hours);
}

export function formatDurationHours(hours) {
  if (hours == null || hours === "") return "Not set";
  const parts = splitDurationHours(hours);
  if (!parts) return "Not set";
  if (Number(hours) === 0) return "0 hours";
  return [
    parts.weeks && `${parts.weeks} ${parts.weeks === 1 ? "week" : "weeks"}`,
    parts.days && `${parts.days} ${parts.days === 1 ? "day" : "days"}`,
    parts.hours && `${parts.hours} ${parts.hours === 1 ? "hour" : "hours"}`,
  ].filter(Boolean).join(" ");
}

export function milestoneLabel(day) {
  if (day == null) return "Timing to be confirmed";
  if (Number(day) === 0) return "At the start";
  if (Number(day) >= 7 && Number(day) % 7 === 0) return `Week ${Number(day) / 7}`;
  return `Day ${day}`;
}

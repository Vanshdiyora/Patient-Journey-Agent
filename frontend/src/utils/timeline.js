export function stepPhase(step) {
  const status = String(step.status || "").toUpperCase();
  if (["COMPLETED", "RESOLVED"].includes(status)) return "completed";
  if (["READY", "IN_PROGRESS", "BLOCKED"].includes(status)) return "current";
  return "upcoming";
}

export function phaseLabel(step) {
  if (String(step.status).toUpperCase() === "CANCELLED") return "Cancelled";
  if (stepPhase(step) === "completed") return "Completed";
  if (String(step.status).toUpperCase() === "BLOCKED") return "Needs attention";
  if (stepPhase(step) === "current") return "Current step";
  return "Coming up";
}

import { isAdmin, isPatient, isStaff } from "../../utils/roles.js";
import { PATHS, buildPath } from "../../routes/paths.js";

export function journeyLink(journeyId, user) {
  if (!journeyId || !user) return null;
  if (isStaff(user)) return buildPath(PATHS.journeyDetail, { journeyId });
  return isPatient(user) ? `${PATHS.myJourney}?journeyId=${encodeURIComponent(journeyId)}` : null;
}

export function patientLink(patientId, user) {
  if (!patientId || !user) return null;
  if (isStaff(user)) return buildPath(PATHS.patientDetail, { patientId });
  return isPatient(user) ? PATHS.myJourney : null;
}

export function metricLink(label, user) {
  if (!isStaff(user)) return null;
  if (label === "Patients") return PATHS.patients;
  if (label === "Open exceptions" || label === "Critical exceptions") return PATHS.exceptions;
  if (label === "Active journeys" || label === "Blocked journeys" || label === "Pending steps") return PATHS.journeys;
  return null;
}

export function usersLink(user) {
  return isAdmin(user) ? PATHS.users : null;
}

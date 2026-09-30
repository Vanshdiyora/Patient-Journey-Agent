/**
 * Role constants and presentation-only capability flags.
 * The backend remains the authority; these gates only control what the UI shows.
 */
export const ROLES = {
  ADMIN: "ADMIN",
  CLINICIAN: "CLINICIAN",
  CARE_COORDINATOR: "CARE_COORDINATOR",
  PATIENT: "PATIENT",
};

export const STAFF_ROLES = [ROLES.ADMIN, ROLES.CLINICIAN, ROLES.CARE_COORDINATOR];

export function roleOf(user) {
  return String(user?.role || "").toUpperCase();
}

export function isStaff(user) {
  return STAFF_ROLES.includes(roleOf(user));
}

export function isPatient(user) {
  return roleOf(user) === ROLES.PATIENT;
}

export function isAdmin(user) {
  return roleOf(user) === ROLES.ADMIN;
}

/** Can the user trigger journey evaluation / orchestration? */
export function canOrchestrate(user) {
  return isStaff(user);
}

/** Can the user resolve exceptions? */
export function canResolveExceptions(user) {
  return isStaff(user);
}

/** Can the user view agent activity / action registry? */
export function canViewObservability(user) {
  return isStaff(user);
}

/** Can the user manage users and configuration? */
export function canManageUsers(user) {
  return isAdmin(user);
}

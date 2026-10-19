/**
 * Central route path constants. Use these instead of string literals so a
 * path change is a one-line edit and links can never drift from the routes.
 */
export const PATHS = {
  home: "/",
  login: "/login",
  account: "/account",
  myJourney: "/my-journey",
  patients: "/patients",
  calendar: "/calendar",
  patientDetail: "/patients/:patientId",
  journeys: "/journeys",
  journeyDetail: "/journeys/:journeyId",
  exceptions: "/exceptions",
  agentRuns: "/agent-runs",
  users: "/users",
  pathways: "/pathways/manage",
};

/** Build a concrete path from a pattern, replacing :params with values. */
export function buildPath(pattern, params = {}) {
  return Object.entries(params).reduce(
    (path, [key, value]) => path.replace(`:${key}`, String(value)),
    pattern
  );
}

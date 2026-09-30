import {
  Activity, AlertTriangle, Bot, HeartPulse, LayoutDashboard, Network,
  UserCog, Users,
} from "lucide-react";
import { ROLES, roleOf } from "../utils/roles";
import { PATHS } from "../routes/paths";

/**
 * Portal identity per role: label shown in the chrome, a theme class that
 * recolors the shell, the nav items each portal shows, and the role label
 * rendered beside the user's name in the sidebar.
 * Everything here is presentation-only; the backend still authorizes every API.
 */
export const PORTALS = {
  [ROLES.ADMIN]: {
    id: "admin",
    label: "Admin Console",
    roleLabel: "Admin",
    theme: "theme-admin",
    items: [
      { to: PATHS.home, label: "Overview", icon: LayoutDashboard, end: true },
      { to: PATHS.patients, label: "Patients", icon: Users },
      { to: PATHS.journeys, label: "Patient journeys", icon: Network },
      { to: PATHS.exceptions, label: "Exceptions", icon: AlertTriangle },
      { to: PATHS.agentRuns, label: "Agent activity", icon: Bot },
      { to: PATHS.actions, label: "Action registry", icon: Activity },
      { to: PATHS.users, label: "User management", icon: UserCog, adminOnly: true },
    ],
  },
  [ROLES.CLINICIAN]: {
    id: "clinician",
    label: "Clinician Portal",
    roleLabel: "Clinician",
    theme: "theme-clinician",
    items: [
      { to: PATHS.home, label: "Clinical overview", icon: LayoutDashboard, end: true },
      { to: PATHS.patients, label: "My patients", icon: Users },
      { to: PATHS.journeys, label: "Journeys", icon: Network },
      { to: PATHS.exceptions, label: "Clinical exceptions", icon: AlertTriangle },
    ],
  },
  [ROLES.CARE_COORDINATOR]: {
    id: "coordinator",
    label: "Coordination Portal",
    roleLabel: "Care Coordinator",
    theme: "theme-coordinator",
    items: [
      { to: PATHS.home, label: "Coordination overview", icon: LayoutDashboard, end: true },
      { to: PATHS.patients, label: "Patients", icon: Users },
      { to: PATHS.journeys, label: "Journeys", icon: Network },
      { to: PATHS.exceptions, label: "Follow-up queue", icon: AlertTriangle },
      { to: PATHS.actions, label: "Task history", icon: Activity },
    ],
  },
  [ROLES.PATIENT]: {
    id: "patient",
    label: "My Health",
    roleLabel: "Patient",
    theme: "theme-patient",
    items: [
      { to: PATHS.myJourney, label: "My Journey", icon: HeartPulse, end: true },
    ],
  },
};

export function portalFor(user) {
  return PORTALS[roleOf(user)] || PORTALS[ROLES.PATIENT];
}

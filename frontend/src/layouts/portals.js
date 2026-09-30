import {
  Activity, AlertTriangle, Bot, HeartPulse, LayoutDashboard, Network,
  UserCog, Users,
} from "lucide-react";
import { ROLES, roleOf } from "../utils/roles";

const STAFF = [ROLES.ADMIN, ROLES.CLINICIAN, ROLES.CARE_COORDINATOR];

/**
 * Portal identity per role: label shown in the chrome, a theme class that
 * recolors the shell, and the nav items each portal shows.
 * `visible` is presentation-only; the backend still authorizes every API.
 */
export const PORTALS = {
  [ROLES.ADMIN]: {
    id: "admin",
    label: "Admin Console",
    theme: "theme-admin",
    items: [
      { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
      { to: "/patients", label: "Patients", icon: Users },
      { to: "/journeys", label: "Patient journeys", icon: Network },
      { to: "/exceptions", label: "Exceptions", icon: AlertTriangle },
      { to: "/agent-runs", label: "Agent activity", icon: Bot },
      { to: "/actions", label: "Action registry", icon: Activity },
      { to: "/users", label: "User management", icon: UserCog, adminOnly: true },
    ],
  },
  [ROLES.CLINICIAN]: {
    id: "clinician",
    label: "Clinician Portal",
    theme: "theme-clinician",
    items: [
      { to: "/", label: "Clinical overview", icon: LayoutDashboard, end: true },
      { to: "/patients", label: "My patients", icon: Users },
      { to: "/journeys", label: "Journeys", icon: Network },
      { to: "/exceptions", label: "Clinical exceptions", icon: AlertTriangle },
    ],
  },
  [ROLES.CARE_COORDINATOR]: {
    id: "coordinator",
    label: "Coordination Portal",
    theme: "theme-coordinator",
    items: [
      { to: "/", label: "Coordination overview", icon: LayoutDashboard, end: true },
      { to: "/patients", label: "Patients", icon: Users },
      { to: "/journeys", label: "Journeys", icon: Network },
      { to: "/exceptions", label: "Follow-up queue", icon: AlertTriangle },
      { to: "/actions", label: "Task history", icon: Activity },
    ],
  },
  [ROLES.PATIENT]: {
    id: "patient",
    label: "My Health",
    theme: "theme-patient",
    items: [
      { to: "/my-journey", label: "My Journey", icon: HeartPulse, end: true },
    ],
  },
};

export function portalFor(user) {
  return PORTALS[roleOf(user)] || PORTALS[ROLES.PATIENT];
}

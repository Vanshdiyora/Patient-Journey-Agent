import { AlertTriangle } from "lucide-react";

/**
 * Role-specific directory tabs. Each tab maps to a backend `filter` value that
 * narrows patients by journey state; the role only decides WHICH tabs are
 * offered. The backend authorizes the request and scopes the rows either way.
 */
export const TABS_BY_ROLE = {
  // Admin: full operational slices across the platform.
  ADMIN: [
    { id: "", label: "All patients" },
    { id: "high_priority", label: "High priority" },
    { id: "blocked", label: "Blocked" },
    { id: "has_exceptions", label: "With exceptions", icon: AlertTriangle },
    { id: "active", label: "Active journeys" },
  ],
  // Clinician: the directory plus patients in this clinician's care.
  CLINICIAN: [
    { id: "", label: "All patients" },
    { id: "mine", label: "My patients" },
    { id: "blocked", label: "Blocked care" },
  ],
  // Coordinator: coordination queue oriented slices.
  CARE_COORDINATOR: [
    { id: "", label: "All patients" },
    { id: "has_exceptions", label: "Follow-ups", icon: AlertTriangle },
    { id: "blocked", label: "Blocked" },
    { id: "active", label: "Active journeys" },
  ],
};

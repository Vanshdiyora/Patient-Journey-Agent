// DB enum values (exceptions.status / exceptions.severity); the backend
// normalizes case, so lowercase values work. "Dismissed" is excluded from the
// default filter list since it is an admin-style disposition.
export const STATUS_OPTIONS = [
  { value: "open", label: "Open" },
  { value: "in_progress", label: "In progress" },
  { value: "resolved", label: "Resolved" },
];

export const SEVERITY_OPTIONS = [
  { value: "critical", label: "Critical" },
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

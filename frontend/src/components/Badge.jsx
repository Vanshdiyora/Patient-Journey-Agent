import React from "react";
import { statusClass, priorityClass, severityClass, humanize } from "../utils";

/**
 * Badge â€” colored pill for status / priority / severity values.
 */
export default function Badge({ kind = "status", value, fallback }) {
  const cls =
    kind === "priority" ? priorityClass(value) :
    kind === "severity" ? severityClass(value) :
    statusClass(value);
  return <span className={cls}>{fallback || humanize(value)}</span>;
}

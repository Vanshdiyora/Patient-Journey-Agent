import React from "react";
import { Activity } from "lucide-react";

/**
 * AlertBanner â€” inline feedback banner after actions (evaluate/orchestrate/events).
 */
export default function AlertBanner({ tone = "error", children }) {
  return (
    <div className={`alert-banner ${tone === "success" ? "alert-banner--success" : "alert-banner--error"}`}>
      <Activity size={18} />
      <span>{children}</span>
    </div>
  );
}

import React from "react";
import { ArrowUpRight } from "lucide-react";

/**
 * MetricCard â€” dashboard KPI card with icon, label, value and hint.
 */
export default function MetricCard({ icon: Icon, label, value, hint, tone = "teal" }) {
  return (
    <div className="metric-card">
      <div className={`metric-icon metric-icon--${tone}`}><Icon size={20} /></div>
      <div className="metric-copy">
        <span>{label}</span>
        <strong>{value ?? "â€”"}</strong>
        {hint && <small>{hint}</small>}
      </div>
      <ArrowUpRight size={17} className="metric-arrow" />
    </div>
  );
}

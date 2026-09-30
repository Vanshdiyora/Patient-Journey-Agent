import React from "react";
import { COMPLETED_STATES } from "./StepsTimeline";

/** Progress header card shared by journey surfaces. */
export default function JourneyProgress({ steps }) {
  const done = steps.filter(s => COMPLETED_STATES.includes(String(s.status).toLowerCase())).length;
  const pct = steps.length ? Math.round((done / steps.length) * 100) : 0;
  return (
    <div className="journey-progress">
      <div className="journey-progress-head"><span>Journey progress</span><strong>{done} / {steps.length} steps completed</strong></div>
      <div className="progress-track"><div className="progress-value" style={{ width: `${pct}%` }} /></div>
    </div>
  );
}

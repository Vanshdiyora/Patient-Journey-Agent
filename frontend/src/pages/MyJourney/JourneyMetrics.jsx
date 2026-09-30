import React from "react";
import { CheckCircle2, Clock3, FileText, HeartPulse } from "lucide-react";
import { formatDate } from "../../utils";

/** Patient overview KPI cards. */
export default function JourneyMetrics({ stepRows, eventRows, nextStep, done }) {
  return (
    <section className="metric-grid">
      <div className="metric-card">
        <div className="metric-icon metric-icon--teal"><HeartPulse size={20} /></div>
        <div className="metric-copy"><span>Care plan progress</span><strong>{stepRows.length ? Math.round(done / stepRows.length * 100) : 0}%</strong><small>{done} of {stepRows.length} steps done</small></div>
      </div>
      <div className="metric-card">
        <div className="metric-icon metric-icon--blue"><Clock3 size={20} /></div>
        <div className="metric-copy"><span>Next step</span><strong>{nextStep ? `Step ${stepRows.indexOf(nextStep) + 1}` : "All done"}</strong><small>{nextStep?.due_at ? `Due ${formatDate(nextStep.due_at)}` : "No pending steps"}</small></div>
      </div>
      <div className="metric-card">
        <div className="metric-icon metric-icon--amber"><FileText size={20} /></div>
        <div className="metric-copy"><span>Updates sent</span><strong>{eventRows.length}</strong><small>{eventRows.filter(e => !e.processed).length} awaiting review</small></div>
      </div>
      <div className="metric-card">
        <div className="metric-icon metric-icon--green"><CheckCircle2 size={20} /></div>
        <div className="metric-copy"><span>Reviewed by team</span><strong>{eventRows.filter(e => e.processed).length}</strong><small>Updates processed</small></div>
      </div>
    </section>
  );
}

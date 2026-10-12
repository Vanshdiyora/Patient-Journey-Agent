import React from "react";
import { CheckCircle2, Clock3, FileText, HeartPulse } from "lucide-react";
import { formatDate } from "../../utils";

/** Patient overview KPI cards. */
export default function JourneyMetrics({ stepRows, eventTotal, processedTotal, nextStep, done }) {
  return (
    <section className="metric-grid">
      <div className="metric-card">
        <div className="metric-icon metric-icon--teal"><HeartPulse size={20} /></div>
        <div className="metric-copy"><span>Care plan progress</span><strong>{stepRows.length ? Math.round(done / stepRows.length * 100) : 0}%</strong><small>{done} of {stepRows.length} steps done</small></div>
      </div>
      <div className="metric-card">
        <div className="metric-icon metric-icon--blue"><Clock3 size={20} /></div>
        <div className="metric-copy"><span>Next step</span><strong>{nextStep ? nextStep.name || `Step ${stepRows.indexOf(nextStep) + 1}` : "All done"}</strong><small>{nextStep?.due_at ? `Action due ${formatDate(nextStep.due_at)}` : nextStep?.planned_due_at ? `Pathway target ${formatDate(nextStep.planned_due_at)}` : "No pending steps"}</small></div>
      </div>
      <div className="metric-card">
        <div className="metric-icon metric-icon--amber"><FileText size={20} /></div>
        <div className="metric-copy"><span>Updates sent</span><strong>{eventTotal}</strong><small>{eventTotal - processedTotal} awaiting review</small></div>
      </div>
      <div className="metric-card">
        <div className="metric-icon metric-icon--green"><CheckCircle2 size={20} /></div>
        <div className="metric-copy"><span>Reviewed by team</span><strong>{processedTotal}</strong><small>Updates processed</small></div>
      </div>
    </section>
  );
}

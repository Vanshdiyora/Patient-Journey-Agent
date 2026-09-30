import React from "react";
import { AlertTriangle, CheckCircle2, Clock3, Play } from "lucide-react";
import { formatDate } from "../../utils";
import { Badge, EmptyState } from "../../components";

const COMPLETED_STATES = ["completed", "resolved"];

/** Ordered pathway-step timeline with status markers. */
export default function StepsTimeline({ steps }) {
  if (!steps.length) return <EmptyState small title="No steps returned" />;
  return (
    <div className="timeline">{steps.map((s, i) => (
      <div className={`timeline-item ${String(s.status).toLowerCase()}`} key={s.id}>
        <div className="timeline-marker">
          {COMPLETED_STATES.includes(String(s.status).toLowerCase()) ? <CheckCircle2 size={17} /> : i === 0 ? <Play size={15} /> : <Clock3 size={16} />}
        </div>
        <div className="timeline-content">
          <div className="timeline-top"><strong>Step {i + 1}</strong><Badge kind="status" value={s.status} /></div>
          <span className="timeline-sub">{s.pathway_step_id}</span>
          {s.block_reason && <div className="block-note"><AlertTriangle size={14} />{s.block_reason}</div>}
          <div className="timeline-dates">
            {s.started_at && <span>Started {formatDate(s.started_at, true)}</span>}
            {s.due_at && <span>Due {formatDate(s.due_at, true)}</span>}
          </div>
        </div>
      </div>
    ))}</div>
  );
}

export { COMPLETED_STATES };

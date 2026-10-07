import React, { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Clock3, Play } from "lucide-react";
import { formatDate } from "../../utils";
import { Badge, EmptyState } from "../../components";

const COMPLETED_STATES = ["completed", "resolved"];

/** Ordered pathway-step timeline with status markers. */
export default function StepsTimeline({ steps, onUpdateTimeLimit, busyStepId }) {
  const [limits, setLimits] = useState({});
  useEffect(() => {
    setLimits(Object.fromEntries(steps.map(step => [step.id, step.time_limit_hours ?? ""])));
  }, [steps]);

  if (!steps.length) return <EmptyState small title="No steps returned" />;
  return (
    <div className="timeline">{steps.map((s, i) => (
      <div className={`timeline-item ${String(s.status).toLowerCase()}`} key={s.id}>
        <div className="timeline-marker">
          {COMPLETED_STATES.includes(String(s.status).toLowerCase()) ? <CheckCircle2 size={17} /> : i === 0 ? <Play size={15} /> : <Clock3 size={16} />}
        </div>
        <div className="timeline-content">
          <div className="timeline-top"><strong>{s.name || `Step ${i + 1}`}</strong><Badge kind="status" value={s.status} /></div>
          {s.description && <span className="timeline-sub">{s.description}</span>}
          {s.block_reason && <div className="block-note"><AlertTriangle size={14} />{s.block_reason}</div>}
          <div className="timeline-dates">
            {s.time_limit_hours != null && <span>Time limit {s.time_limit_hours} hour{s.time_limit_hours === 1 ? "" : "s"} from ready</span>}
            {s.started_at && <span>Started {formatDate(s.started_at, true)}</span>}
            {s.due_at && <span>Due {formatDate(s.due_at, true)}</span>}
          </div>
          {onUpdateTimeLimit && !COMPLETED_STATES.includes(String(s.status).toLowerCase()) && !["cancelled"].includes(String(s.status).toLowerCase()) && (
            <form
              className="step-time-limit-form"
              onSubmit={event => {
                event.preventDefault();
                onUpdateTimeLimit(s.id, Number(limits[s.id]));
              }}
            >
              <label>
                Time limit (hours)
                <input
                  type="number"
                  min="1"
                  max="8760"
                  required
                  value={limits[s.id] ?? ""}
                  onChange={event => setLimits(current => ({ ...current, [s.id]: event.target.value }))}
                  disabled={busyStepId === s.id}
                />
              </label>
              <button className="secondary-btn" type="submit" disabled={busyStepId === s.id || !limits[s.id]}>
                {busyStepId === s.id ? "Saving…" : "Update limit"}
              </button>
            </form>
          )}
          {onUpdateTimeLimit && <div className="step-time-limit-note">A saved change restarts the deadline from now if the step is already ready.</div>}
        </div>
      </div>
    ))}</div>
  );
}

export { COMPLETED_STATES };

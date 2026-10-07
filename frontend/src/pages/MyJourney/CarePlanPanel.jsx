import React from "react";
import { CalendarClock, CheckCircle2 } from "lucide-react";
import { formatDate } from "../../utils";
import { Badge, EmptyState, Panel, SkeletonRows } from "../../components";

/** Care plan timeline for the signed-in patient's own journey. */
export default function CarePlanPanel({ steps, stepRows }) {
  return (
    <Panel wide title="My care plan" subtitle="What you're working on">
      {steps.loading ? <SkeletonRows /> : stepRows.length ? (
        <div className="timeline">{stepRows.map((s, i) => (
          <div className={`timeline-item ${String(s.status).toLowerCase()}`} key={s.id}>
            <div className="timeline-marker">
              {["COMPLETED", "RESOLVED"].includes(String(s.status).toUpperCase()) ? <CheckCircle2 size={17} /> : <CalendarClock size={15} />}
            </div>
            <div className="timeline-content">
              <div className="timeline-top"><strong>{s.name || `Step ${i + 1}`}</strong><Badge kind="status" value={s.status} /></div>
              {s.description && <span className="timeline-sub">{s.description}</span>}
              <div className="timeline-dates">
                {s.time_limit_hours != null && <span>Time limit {s.time_limit_hours} hour{s.time_limit_hours === 1 ? "" : "s"} from ready</span>}
                {s.started_at && <span>Started {formatDate(s.started_at, true)}</span>}
                {s.due_at && <span>Due {formatDate(s.due_at, true)}</span>}
              </div>
            </div>
          </div>
        ))}</div>
      ) : <EmptyState small title="No steps yet" text="Your care plan is being prepared." />}
    </Panel>
  );
}

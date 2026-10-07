import React, { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Clock3, Play } from "lucide-react";
import { formatDate, humanize } from "../../utils";
import { Badge, EmptyState } from "../../components";

const COMPLETED_STATES = ["completed", "resolved"];
const STAFF_ROLES = new Set(["ADMIN", "CLINICIAN", "CARE_COORDINATOR"]);
const ROLE_PERMISSIONS = {
  ADMIN: new Set(["ADMIN"]),
  CLINICIAN: new Set(["ADMIN", "CLINICIAN"]),
  CARE_COORDINATOR: new Set(["ADMIN", "CARE_COORDINATOR"]),
};

function canUserCompleteStep(step, role) {
  const ownerRole = String(step.owner_role || "STAFF").toUpperCase();
  if (ownerRole === "AGENT") return false;
  if (ownerRole === "PATIENT") return Boolean(step.patient_submission_pending) && STAFF_ROLES.has(role);
  return (ROLE_PERMISSIONS[ownerRole] || STAFF_ROLES).has(role);
}

function TimelineItem({ step, index, onUpdateTimeLimit, onComplete, busyStepId, userRole, limit, setLimit }) {
  const isCompleted = COMPLETED_STATES.includes(String(step.status).toLowerCase());
  const status = String(step.status).toUpperCase();
  const canComplete = ["READY", "IN_PROGRESS"].includes(status) && canUserCompleteStep(step, userRole);
  const ownerRole = String(step.owner_role || "STAFF").toUpperCase();
  let marker = <Clock3 size={16} />;
  if (isCompleted) marker = <CheckCircle2 size={17} />;
  else if (index === 0) marker = <Play size={15} />;

  let completionLabel = "Mark completed";
  if (busyStepId === step.id) completionLabel = "Saving…";
  else if (ownerRole === "PATIENT") completionLabel = "Review & complete";

  return (
    <div className={`timeline-item ${String(step.status).toLowerCase()}`} key={step.id}>
      <div className="timeline-marker">{marker}</div>
      <div className="timeline-content">
        <div className="timeline-top"><strong>{step.name || `Step ${index + 1}`}</strong><Badge kind="status" value={step.status} /></div>
        {step.description && <span className="timeline-sub">{step.description}</span>}
        <span className="timeline-sub">Responsible: {humanize(ownerRole)}</span>
        {ownerRole === "PATIENT" && step.patient_submission_pending && <span className="timeline-sub">Patient update received; awaiting staff review</span>}
        {ownerRole === "AGENT" && <span className="timeline-sub">Agent tasks complete only after a verified action succeeds</span>}
        {step.block_reason && <div className="block-note"><AlertTriangle size={14} />{step.block_reason}</div>}
        <div className="timeline-dates">
          {step.time_limit_hours != null && <span>Time limit {step.time_limit_hours} hour{step.time_limit_hours === 1 ? "" : "s"} from ready</span>}
          {step.started_at && <span>Started {formatDate(step.started_at, true)}</span>}
          {step.due_at && <span>Due {formatDate(step.due_at, true)}</span>}
        </div>
        {onUpdateTimeLimit && !isCompleted && status !== "CANCELLED" && (
          <form
            className="step-time-limit-form"
            onSubmit={event => {
              event.preventDefault();
              onUpdateTimeLimit(step.id, Number(limit));
            }}
          >
            <label>
              Time limit (hours)
              <input
                type="number"
                min="1"
                max="8760"
                required
                value={limit ?? ""}
                onChange={event => setLimit(step.id, event.target.value)}
                disabled={busyStepId === step.id}
              />
            </label>
            <button className="secondary-btn" type="submit" disabled={busyStepId === step.id || !limit}>
              {busyStepId === step.id ? "Saving…" : "Update limit"}
            </button>
          </form>
        )}
        {onUpdateTimeLimit && <div className="step-time-limit-note">A saved change restarts the deadline from now if the step is already ready.</div>}
        {onComplete && canComplete && (
          <button
            className="secondary-btn step-complete-btn"
            type="button"
            onClick={() => onComplete(step)}
            disabled={busyStepId === step.id}
          >
            <CheckCircle2 size={14} />{completionLabel}
          </button>
        )}
      </div>
    </div>
  );
}

/** Ordered pathway-step timeline with status markers. */
export default function StepsTimeline({ steps, onUpdateTimeLimit, onComplete, busyStepId, userRole }) {
  const [limits, setLimits] = useState({});
  useEffect(() => {
    setLimits(Object.fromEntries(steps.map(step => [step.id, step.time_limit_hours ?? ""])));
  }, [steps]);

  if (!steps.length) return <EmptyState small title="No steps returned" />;
  const role = String(userRole || "").toUpperCase();
  const setLimit = (stepId, value) => setLimits(current => ({ ...current, [stepId]: value }));
  return (
    <div className="timeline">
      {steps.map((step, index) => (
        <TimelineItem
          key={step.id}
          step={step}
          index={index}
          onUpdateTimeLimit={onUpdateTimeLimit}
          onComplete={onComplete}
          busyStepId={busyStepId}
          userRole={role}
          limit={limits[step.id]}
          setLimit={setLimit}
        />
      ))}
    </div>
  );
}

export { COMPLETED_STATES };

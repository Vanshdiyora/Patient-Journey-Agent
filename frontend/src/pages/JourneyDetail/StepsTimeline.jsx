import React, { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Clock3, Play } from "lucide-react";
import { formatDate, humanize } from "../../utils";
import { EmptyState } from "../../components";
import StepEvidenceForm from "./StepEvidenceForm";
import { phaseLabel, stepPhase } from "../../utils/timeline";
import { formatDurationHours, milestoneLabel } from "../../utils/duration";
import DurationInput from "../../components/DurationInput";

const COMPLETED_STATES = ["completed", "resolved"];
const ROLE_PERMISSIONS = {
  ADMIN: new Set(["ADMIN"]),
  CLINICIAN: new Set(["CLINICIAN"]),
  CARE_COORDINATOR: new Set(["CARE_COORDINATOR"]),
};

function canUserCompleteStep(step, role) {
  const ownerRole = String(step.owner_role || "CLINICIAN").toUpperCase();
  if (ownerRole === "AGENT") return false;
  if (ownerRole === "PATIENT") return Boolean(step.patient_submission_pending) && role === "CLINICIAN";
  return ROLE_PERMISSIONS[ownerRole]?.has(role) || false;
}

function canUserSubmitEvidence(step, role) {
  const ownerRole = String(step.owner_role || "CLINICIAN").toUpperCase();
  return ROLE_PERMISSIONS[ownerRole]?.has(role) || false;
}

function completionHint(step) {
  const ownerRole = String(step.owner_role || "CLINICIAN").toUpperCase();
  if (ownerRole === "PATIENT") {
    return step.patient_submission_pending
      ? "Awaiting clinician review"
      : "Waiting for patient submission";
  }
  if (ownerRole === "AGENT") {
    return "Waiting for verified agent action";
  }
  if (!ROLE_PERMISSIONS[ownerRole]) return "Cannot complete: invalid responsible role";
  return `Waiting for ${humanize(ownerRole)}`;
}

function TimelineItem({ step, index, onUpdateTimeLimit, onComplete, onAddEvidence, busyStepId, userRole, limit, setLimit }) {
  const isCompleted = COMPLETED_STATES.includes(String(step.status).toLowerCase());
  const status = String(step.status).toUpperCase();
  const canComplete = ["READY", "IN_PROGRESS"].includes(status) && canUserCompleteStep(step, userRole);
  const ownerRole = String(step.owner_role || "CLINICIAN").toUpperCase();
  let marker = <Clock3 size={16} />;
  if (isCompleted) marker = <CheckCircle2 size={17} />;
  else if (stepPhase(step) === "current") marker = <Play size={15} />;

  let completionLabel = "Mark completed";
  if (busyStepId === step.id) completionLabel = "Saving…";
  else if (ownerRole === "PATIENT") completionLabel = "Review & complete";

  return (
    <div className={`timeline-item timeline-item--${stepPhase(step)} ${String(step.status).toLowerCase()}`} key={step.id}>
      <div className="timeline-marker">{marker}</div>
      <div className="timeline-content">
        <div className="timeline-top"><strong><span className="timeline-step-number">{index + 1}.</span> {step.name || `Step ${index + 1}`}</strong><span className={`timeline-phase timeline-phase--${stepPhase(step)}`}>{phaseLabel(step)}</span></div>
        {step.description && <span className="timeline-sub">{step.description}</span>}
        <span className="timeline-sub">Responsible: {humanize(ownerRole)}</span>
        {ownerRole === "PATIENT" && step.patient_submission_pending && <span className="timeline-sub">Patient update received; awaiting clinician review</span>}
        {ownerRole === "AGENT" && <span className="timeline-sub">Agent tasks complete only after a verified action succeeds</span>}
        {step.block_reason && <div className="block-note"><AlertTriangle size={14} />{step.block_reason}</div>}
        {onAddEvidence && canUserSubmitEvidence(step, userRole) && ["READY", "IN_PROGRESS"].includes(status) && (
          <StepEvidenceForm
            step={step}
            busy={busyStepId === step.id}
            evidenceType="RESULT"
            onSubmit={onAddEvidence}
          />
        )}
        {onAddEvidence && canUserSubmitEvidence(step, userRole) && status === "BLOCKED" && ["Required result evidence is missing", "Required approval evidence is missing"].includes(step.block_reason) && (
          <StepEvidenceForm
            step={step}
            busy={busyStepId === step.id}
            evidenceType={step.block_reason === "Required approval evidence is missing" ? "APPROVAL" : "RESULT"}
            onSubmit={onAddEvidence}
          />
        )}
        <div className="timeline-dates">
          {step.planned_due_at && <span>Pathway target: {milestoneLabel(step.due_after_days)} · {formatDate(step.planned_due_at)}</span>}
          {isCompleted && step.completed_at && <span>Completed {formatDate(step.completed_at, true)}</span>}
          {!isCompleted && step.started_at && <span>Started {formatDate(step.started_at, true)}</span>}
          {stepPhase(step) === "current" && step.due_at && <span>Action due {formatDate(step.due_at, true)}</span>}
          {stepPhase(step) === "upcoming" && !step.planned_due_at && <span>Available after earlier steps</span>}
          {step.time_limit_hours != null && !isCompleted && <span>{formatDurationHours(step.time_limit_hours)} allowed once ready</span>}
        </div>
        {onUpdateTimeLimit && !isCompleted && status !== "CANCELLED" && (
          <form
            className="step-time-limit-form"
            onSubmit={event => {
              event.preventDefault();
              onUpdateTimeLimit(step.id, Number(limit));
            }}
          >
            <DurationInput label="Time allowed once ready" hours={limit ?? ""} onChange={value => setLimit(step.id, value)} disabled={busyStepId === step.id} />
            <button className="secondary-btn" type="submit" disabled={busyStepId === step.id || !limit}>
              {busyStepId === step.id ? "Saving…" : "Update limit"}
            </button>
          </form>
        )}
        {onUpdateTimeLimit && !isCompleted && status !== "CANCELLED" && <div className="step-time-limit-note">Changing this allowance restarts the action deadline for a ready step.</div>}
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
        {onComplete && !isCompleted && ["READY", "IN_PROGRESS"].includes(status) && !canComplete && (
          <button className="secondary-btn step-complete-btn" type="button" disabled>
            <Clock3 size={14} />{completionHint(step)}
          </button>
        )}
      </div>
    </div>
  );
}

/** Ordered pathway-step timeline with status markers. */
export default function StepsTimeline({ steps, onUpdateTimeLimit, onComplete, onAddEvidence, busyStepId, userRole }) {
  const [limits, setLimits] = useState({});
  useEffect(() => {
    setLimits(Object.fromEntries(steps.map(step => [step.id, step.time_limit_hours ?? ""])));
  }, [steps]);

  if (!steps.length) return <EmptyState small title="No steps returned" />;
  const role = String(userRole || "").toUpperCase();
  const setLimit = (stepId, value) => setLimits(current => ({ ...current, [stepId]: value }));
  const completed = steps.filter(step => stepPhase(step) === "completed").length;
  return (
    <div className="timeline"><div className="timeline-summary">{completed} of {steps.length} steps completed</div>
      {steps.map((step, index) => (
        <TimelineItem
          key={step.id}
          step={step}
          index={index}
          onUpdateTimeLimit={onUpdateTimeLimit}
          onComplete={onComplete}
          onAddEvidence={onAddEvidence}
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

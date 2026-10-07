import React, { useState } from "react";
import { CalendarClock, CheckCircle2, Send } from "lucide-react";
import { formatDate, getErrorMessage, humanize } from "../../utils";
import { Badge, EmptyState, Panel, SkeletonRows } from "../../components";

function CarePlanStep({ step, index, comments, setComments, busyStepId, onSubmitStep }) {
  const patientOwned = String(step.owner_role || "").toUpperCase() === "PATIENT";
  const status = String(step.status).toUpperCase();
  const available = ["READY", "IN_PROGRESS"].includes(status);
  const completed = ["COMPLETED", "RESOLVED"].includes(status);
  const submit = async event => {
    event.preventDefault();
    const submitted = await onSubmitStep(step.id, comments[step.id] || "");
    if (submitted) setComments(current => ({ ...current, [step.id]: "" }));
  };

  return (
    <div className={`timeline-item ${String(step.status).toLowerCase()}`} key={step.id}>
      <div className="timeline-marker">{completed ? <CheckCircle2 size={17} /> : <CalendarClock size={15} />}</div>
      <div className="timeline-content">
        <div className="timeline-top"><strong>{step.name || `Step ${index + 1}`}</strong><Badge kind="status" value={step.status} /></div>
        {step.description && <span className="timeline-sub">{step.description}</span>}
        {step.owner_role && <span className="timeline-sub">Responsible: {humanize(step.owner_role)}</span>}
        <div className="timeline-dates">
          {step.time_limit_hours != null && <span>Time limit {step.time_limit_hours} hour{step.time_limit_hours === 1 ? "" : "s"} from ready</span>}
          {step.started_at && <span>Started {formatDate(step.started_at, true)}</span>}
          {step.due_at && <span>Due {formatDate(step.due_at, true)}</span>}
        </div>
        {patientOwned && step.patient_submission_pending && (
          <div className="step-time-limit-note">Your update was sent and is awaiting care-team review.</div>
        )}
        {patientOwned && available && !step.patient_submission_pending && (
          <form className="patient-step-submit" onSubmit={submit}>
            <label htmlFor={`step-comment-${step.id}`}>Tell your care team how you completed this task</label>
            <textarea
              id={`step-comment-${step.id}`}
              required
              maxLength={2000}
              value={comments[step.id] || ""}
              onChange={event => setComments(current => ({ ...current, [step.id]: event.target.value }))}
            />
            <button className="secondary-btn" type="submit" disabled={busyStepId === step.id}>
              <Send size={14} />{busyStepId === step.id ? "Submitting…" : "Submit for review"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

/** Care plan timeline for the signed-in patient's own journey. */
export default function CarePlanPanel({ steps, stepRows, onSubmitStep }) {
  const [comments, setComments] = useState({});
  const [busyStepId, setBusyStepId] = useState("");
  const [error, setError] = useState("");
  const submitStep = async (stepId, comment) => {
    setBusyStepId(stepId);
    setError("");
    try {
      await onSubmitStep(stepId, comment);
      return true;
    } catch (submitError) {
      setError(getErrorMessage(submitError));
      return false;
    } finally {
      setBusyStepId("");
    }
  };

  let content = <EmptyState small title="No steps yet" text="Your care plan is being prepared." />;
  if (steps.loading) content = <SkeletonRows />;
  else if (stepRows.length) {
    content = (
      <div className="timeline">{stepRows.map((step, index) => (
        <CarePlanStep
          key={step.id}
          step={step}
          index={index}
          comments={comments}
          setComments={setComments}
          busyStepId={busyStepId}
          onSubmitStep={submitStep}
        />
      ))}</div>
    );
  }

  return (
    <Panel wide title="My care plan" subtitle="What you're working on">
      {error && <div className="form-error" role="alert">{error}</div>}
      {content}
    </Panel>
  );
}

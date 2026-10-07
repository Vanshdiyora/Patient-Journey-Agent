import React from "react";
import { AlertTriangle, Ban, Check, Clock, Loader2, User, Wrench } from "lucide-react";
import { readResultPresentation } from "./presentation";

const ROLE_LABELS = {
  search_patients: "Search patients",
  get_patient_summary: "Patient summary",
  list_pathways: "Care pathways",
  get_pending_tasks: "Open tasks",
  start_pathway: "Start a pathway",
  submit_event: "Record an update",
  orchestrate_journey: "Re-evaluate journey",
  list_journeys: "Look up journeys",
  get_journey_steps: "Look up journey steps",
};

const STATUS_DONE = new Set(["completed", "cancelled"]);

function statusSymbol(status) {
  const s = (status || "").toLowerCase();
  if (s === "completed") return "✓";
  if (s === "in_progress" || s === "ready") return "→";
  if (s === "blocked") return "!";
  return "○";
}

function chipClass(status) {
  const s = (status || "").toLowerCase();
  if (s === "completed" || s === "active") return "chat-chip chat-chip--ok";
  if (s === "blocked" || s === "cancelled") return "chat-chip chat-chip--warn";
  if (s === "in_progress" || s === "ready") return "chat-chip chat-chip--info";
  return "chat-chip";
}

function fmtDate(value) {
  if (!value) return null;
  try { return new Date(value).toLocaleDateString(); } catch { return null; }
}

function StepTimeline({ steps, compact }) {
  if (!steps?.length) return null;
  return (
    <ul className={compact ? "chat-steps chat-steps--compact" : "chat-steps"}>
      {steps.map((s, i) => (
        <li key={s.id || i} className={`chat-step chat-step--${(s.status || "").toLowerCase()}`}>
          <span className="chat-step-icon" aria-hidden>{statusSymbol(s.status)}</span>
          <span className="chat-step-name">{s.name || "Step"}</span>
          {s.due_at && !compact && <span className="chat-step-due">due {fmtDate(s.due_at)}</span>}
          {s.block_reason && <span className="chat-step-block" title={s.block_reason}>blocked</span>}
        </li>
      ))}
    </ul>
  );
}

function JourneyRow({ journey }) {
  return (
    <div className="chat-journey-row">
      <div className="chat-journey-main">
        <strong>{journey.pathway_name || "Care journey"}</strong>
        <span className="chat-muted">{journey.patient_name || ""}{journey.patient_reference ? ` · ${journey.patient_reference}` : ""}</span>
      </div>
      <span className={chipClass(journey.status)}>{(journey.status || "").toLowerCase()}</span>
    </div>
  );
}

function PatientCard({ patient }) {
  return (
    <div className="chat-patient-card">
      <User size={14} />
      <div>
        <strong>{patient.name || "Patient"}</strong>
        {patient.reference && <span className="chat-muted"> · {patient.reference}</span>}
      </div>
    </div>
  );
}

/**
 * Structured renderers for read-only tool results — API data becomes UI
 * components, never raw JSON.
 */
function StructuredData({ tool, data }) {
  if (!data) return null;
  if (tool === "search_patients" && data.patients) {
    if (!data.patients.length) return <div className="chat-data-empty">No matching patients.</div>;
    return data.patients.map((p, i) => <PatientCard key={p.id || i} patient={p} />);
  }
  if (tool === "get_patient_summary" && data.patient) {
    return (
      <>
        <PatientCard patient={data.patient} />
        {data.journeys?.length
          ? data.journeys.map((j) => <JourneyRow key={j.id} journey={j} />)
          : <div className="chat-data-empty">No journeys yet.</div>}
      </>
    );
  }
  if (tool === "list_pathways" && data.pathways) {
    return data.pathways.map((w) => (
      <div key={w.id} className="chat-journey-row">
        <div className="chat-journey-main">
          <strong>{w.name}</strong>
          <span className="chat-muted">{w.steps?.length || 0} steps</span>
        </div>
        <span className="chat-chip">active</span>
      </div>
    ));
  }
  if (tool === "list_journeys" && data.journeys) {
    if (!data.journeys.length) return <div className="chat-data-empty">No journeys found.</div>;
    return data.journeys.map((j) => <JourneyRow key={j.id} journey={j} />);
  }
  if (tool === "get_journey_steps" && data.journey) {
    return (
      <>
        <JourneyRow journey={data.journey} />
        <StepTimeline steps={data.steps} />
      </>
    );
  }
  if (tool === "get_pending_tasks" && data.journeys) {
    if (!data.journeys.length) return <div className="chat-data-empty">No open tasks — everything is on track.</div>;
    return data.journeys.map((entry) => (
      <div key={entry.journey_id} className="chat-task-group">
        <div className="chat-journey-main">
          <strong>{entry.pathway_name || "Care journey"}</strong>
          <span className="chat-muted">{entry.patient_name || ""}</span>
        </div>
        <StepTimeline steps={entry.tasks} compact />
      </div>
    ));
  }
  return null;
}

function humanizeTool(name) {
  return ROLE_LABELS[name] || name.replace(/_/g, " ");
}

function prettyArgs(args = {}) {
  if (args.event_type) {
    const parts = [args.event_type.replace(/_/g, " ").toLowerCase()];
    if (args.comment) parts.push(`"${String(args.comment).slice(0, 120)}"`);
    if (args.journey_id) parts.push(`journey ${String(args.journey_id).slice(0, 8)}`);
    return parts.join(" · ");
  }
  if (args.journey_id) return `journey ${String(args.journey_id).slice(0, 8)}`;
  return "";
}

/**
 * One chat bubble. For assistant messages carrying a pending_action, renders
 * the inline Confirm/Reject card; once resolved, shows the outcome state.
 */
export default function ChatMessageItem({ message, busy, onConfirm, onReject }) {
  const isUser = message.role === "user";
  const meta = message.meta || {};
  const pending = meta.pending_action;
  const actionResult = meta.action_result;

  if (isUser) {
    return (
      <div className="chat-row chat-row--user">
        <div className="chat-bubble chat-bubble--user">{message.content}</div>
      </div>
    );
  }

  const presentation = readResultPresentation(message);
  const description = pending?.description || null;
  const showStructured = !pending && !actionResult && presentation.kind === "card";
  const showText = !pending && !actionResult && presentation.kind === "text";

  return (
    <div className="chat-row chat-row--assistant">
      <div className="chat-avatar"><Wrench size={13} /></div>
      <div className="chat-bubble-group">
        {showText && <div className="chat-bubble chat-bubble--assistant">{presentation.text}</div>}

        {showStructured && <div className="chat-data-card">
          <div className="chat-data-label"><Wrench size={11} /> {humanizeTool(presentation.result.tool)}</div>
          <StructuredData tool={presentation.result.tool} data={presentation.result.result.data} />
        </div>}

        {pending && (
          <div className={`chat-action-card chat-action-card--${pending.status}`}>
            <div className="chat-action-head">
              <Wrench size={14} />
              <strong>{description?.title || humanizeTool(pending.name)}</strong>
              {pending.status === "pending" && <span className="chat-action-badge">Awaiting confirmation</span>}
              {pending.status === "executed" && <span className="chat-action-badge chat-action-badge--done"><Check size={11} /> Done</span>}
              {pending.status === "failed" && <span className="chat-action-badge chat-action-badge--fail"><AlertTriangle size={11} /> Failed</span>}
              {pending.status === "rejected" && <span className="chat-action-badge chat-action-badge--muted"><Ban size={11} /> Rejected</span>}
              {pending.status === "expired" && <span className="chat-action-badge chat-action-badge--muted"><Clock size={11} /> Expired</span>}
            </div>
            {description?.patient && (
              <div className="chat-action-args">Patient: {description.patient}</div>
            )}
            {!description?.patient && prettyArgs(pending.arguments) && (
              <div className="chat-action-args">{prettyArgs(pending.arguments)}</div>
            )}
            {description?.changes?.length > 0 && pending.status === "pending" && (
              <ul className="chat-action-changes">
                {description.changes.map((c, i) => <li key={i}>{c}</li>)}
              </ul>
            )}
            {pending.status === "pending" ? (
              <div className="chat-action-buttons">
                <button className="chat-action-confirm" disabled={busy} onClick={onConfirm}>
                  {busy ? <Loader2 size={13} className="chat-spin" /> : <Check size={13} />} Confirm
                </button>
                <button className="chat-action-reject" disabled={busy} onClick={onReject}>
                  <Ban size={13} /> Reject
                </button>
              </div>
            ) : null}
          </div>
        )}

        {!pending && actionResult && (
          <div className={`chat-action-card chat-action-card--${actionResult.status}`}>
            <div className="chat-action-head">
              <Wrench size={14} />
              <strong>{humanizeTool(actionResult.tool)}</strong>
              <span className={`chat-action-badge ${actionResult.status === "executed" ? "chat-action-badge--done" : "chat-action-badge--fail"}`}>
                {actionResult.status === "executed" ? <><Check size={11} /> Completed</>
                  : actionResult.status === "expired" ? <><Clock size={11} /> Expired</>
                  : <><AlertTriangle size={11} /> Failed</>}
              </span>
            </div>
            {actionResult.result?.data?.journey && (
              <div className="chat-data-card">
                <JourneyRow journey={actionResult.result.data.journey} />
              </div>
            )}
            {(actionResult.result?.summary || actionResult.error || message.content) && (
              <div className={`chat-action-outcome ${actionResult.status !== "executed" ? "chat-action-outcome--error" : ""}`}>
                {actionResult.status === "executed" ? actionResult.result?.summary || message.content : actionResult.error || message.content}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

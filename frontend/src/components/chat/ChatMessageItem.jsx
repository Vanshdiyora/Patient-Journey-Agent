import React from "react";
import { AlertTriangle, Ban, Check, ChevronRight, Clock, Loader2, User, Wrench } from "lucide-react";
import { Link } from "react-router-dom";
import { readResultPresentation } from "./presentation";
import ChatMarkdown from "./ChatMarkdown";
import { journeyLink, metricLink, patientLink, usersLink } from "./navigation";

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
  list_patients: "Patients",
  get_journey_events: "Journey events",
  get_dashboard_summary: "Dashboard figures",
  list_exceptions: "Exceptions",
  list_users: "User accounts",
  get_chat_audit: "Chatbot audit trail",
  complete_step: "Complete a step",
  submit_step_update: "Report a task",
  update_step_time_limit: "Change a time limit",
  update_exception: "Update an exception",
  set_user_role: "Change a user's role",
  set_user_status: "Change account status",
  create_pathway: "Create a pathway",
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

function ResultRow({ to, className, onNavigate, children, label }) {
  if (!to) return <div className={className}>{children}</div>;
  return (
    <Link className={`${className} chat-result-link`} to={to} onClick={onNavigate} aria-label={label}>
      {children}<ChevronRight size={13} className="chat-result-chevron" aria-hidden />
    </Link>
  );
}

function JourneyRow({ journey, user, onNavigate }) {
  return (
    <ResultRow className="chat-journey-row" to={journeyLink(journey.id, user)} onNavigate={onNavigate}
      label={`Open ${journey.pathway_name || "care journey"} for ${journey.patient_name || "patient"}`}>
      <div className="chat-journey-main">
        <strong>{journey.pathway_name || "Care journey"}</strong>
        <span className="chat-muted">{journey.patient_name || ""}{journey.patient_reference ? ` · ${journey.patient_reference}` : ""}</span>
      </div>
      <span className={chipClass(journey.status)}>{(journey.status || "").toLowerCase()}</span>
    </ResultRow>
  );
}

function PatientCard({ patient, user, onNavigate }) {
  return (
    <ResultRow className="chat-patient-card" to={patientLink(patient.id, user)} onNavigate={onNavigate}
      label={`Open ${patient.name || "patient"}`}>
      <User size={14} />
      <div>
        <strong>{patient.name || "Patient"}</strong>
        {patient.reference && <span className="chat-muted"> · {patient.reference}</span>}
      </div>
    </ResultRow>
  );
}

/**
 * Structured renderers for read-only tool results — API data becomes UI
 * components, never raw JSON.
 */
function StructuredData({ tool, data, user, onNavigate }) {
  if (!data) return null;
  if (tool === "search_patients" && data.patients) {
    if (!data.patients.length) return <div className="chat-data-empty">No matching patients.</div>;
    return data.patients.map((p, i) => <PatientCard key={p.id || i} patient={p} user={user} onNavigate={onNavigate} />);
  }
  if (tool === "get_patient_summary" && data.patient) {
    return (
      <>
        <PatientCard patient={data.patient} user={user} onNavigate={onNavigate} />
        {data.journeys?.length
          ? data.journeys.map((j, i) => <JourneyRow key={j.id || i} journey={j} user={user} onNavigate={onNavigate} />)
          : <div className="chat-data-empty">No journeys yet.</div>}
      </>
    );
  }
  if (tool === "list_pathways" && data.pathways) {
    return data.pathways.map((w, i) => (
      <details key={w.id || i} className="chat-pathway-detail">
        <summary className="chat-journey-row chat-result-link">
          <span className="chat-journey-main"><strong>{w.name}</strong><span className="chat-muted">{w.steps?.length || 0} steps</span></span>
          <span className="chat-chip">active</span><ChevronRight size={13} className="chat-result-chevron" aria-hidden />
        </summary>
        <div className="chat-pathway-body">
          {w.description && <p>{w.description}</p>}
          {w.steps?.length ? <ol>{w.steps.map((step, index) => <li key={index}>{step}</li>)}</ol> : <span>No steps listed.</span>}
        </div>
      </details>
    ));
  }
  if (tool === "list_journeys" && data.journeys) {
    if (!data.journeys.length) return <div className="chat-data-empty">No journeys found.</div>;
    return data.journeys.map((j, i) => <JourneyRow key={j.id || i} journey={j} user={user} onNavigate={onNavigate} />);
  }
  if (tool === "get_journey_steps" && data.journey) {
    return (
      <>
        <JourneyRow journey={data.journey} user={user} onNavigate={onNavigate} />
        <StepTimeline steps={data.steps} />
      </>
    );
  }
  if (tool === "get_pending_tasks" && data.journeys) {
    if (!data.journeys.length) return <div className="chat-data-empty">No open tasks — everything is on track.</div>;
    return data.journeys.map((entry, i) => (
      <ResultRow key={entry.journey_id || i} className="chat-task-group" to={journeyLink(entry.journey_id, user)} onNavigate={onNavigate}
        label={`Open tasks for ${entry.pathway_name || "care journey"}`}>
        <div className="chat-journey-main">
          <strong>{entry.pathway_name || "Care journey"}</strong>
          <span className="chat-muted">{entry.patient_name || ""}</span>
        </div>
        <StepTimeline steps={entry.tasks} compact />
      </ResultRow>
    ));
  }
  if (tool === "list_patients" && data.patients) {
    return data.patients.map((p, i) => <PatientCard key={p.id || i} patient={p} user={user} onNavigate={onNavigate} />);
  }
  if (tool === "get_journey_events" && data.events) {
    return data.events.map((e, i) => (
      <ResultRow key={e.id || i} className="chat-journey-row" to={journeyLink(data.journey_id, user)} onNavigate={onNavigate}
        label={`Open journey for ${(e.event_type || "event").replace(/_/g, " ")}`}>
        <div className="chat-journey-main">
          <strong>{(e.event_type || "").replace(/_/g, " ").toLowerCase()}</strong>
          <span className="chat-muted">{[fmtDate(e.event_time), e.comment].filter(Boolean).join(" · ")}</span>
        </div>
      </ResultRow>
    ));
  }
  if (tool === "get_dashboard_summary" && data.metrics) {
    const m = data.metrics;
    const rows = [
      ["Active journeys", m.active_journeys], ["Blocked journeys", m.blocked_journeys],
      ["Open exceptions", m.open_exceptions], ["Critical exceptions", m.critical_exceptions],
      ["Pending steps", m.pending_steps], ["Patients", m.total_patients],
    ];
    return rows.map(([label, value]) => (
      <ResultRow key={label} className="chat-journey-row" to={metricLink(label, user)} onNavigate={onNavigate} label={`Open ${label.toLowerCase()}`}>
        <div className="chat-journey-main"><strong>{label}</strong></div>
        <span className="chat-chip">{value ?? 0}</span>
      </ResultRow>
    ));
  }
  if (tool === "list_exceptions" && data.exceptions) {
    return data.exceptions.map((e, i) => (
      <ResultRow key={e.id || i} className="chat-journey-row" to={journeyLink(e.journey_id, user)} onNavigate={onNavigate}
        label={`Open journey for exception ${e.title || ""}`}>
        <div className="chat-journey-main">
          <strong>{e.title}</strong>
          <span className="chat-muted">{e.severity} · {fmtDate(e.created_at)}</span>
        </div>
        <span className={chipClass(e.status === "open" ? "blocked" : e.status === "resolved" ? "completed" : e.status)}>
          {(e.status || "").replace(/_/g, " ")}
        </span>
      </ResultRow>
    ));
  }
  if (tool === "list_users" && data.users) {
    return data.users.map((u, i) => (
      <ResultRow key={u.id || i} className="chat-journey-row" to={usersLink(user)} onNavigate={onNavigate}
        label={`Open user management for ${u.display_name || u.email}`}>
        <div className="chat-journey-main">
          <strong>{u.display_name}</strong>
          <span className="chat-muted">{u.email} · {(u.role || "").replace(/_/g, " ").toLowerCase()}</span>
        </div>
        <span className={chipClass(u.is_active ? "active" : "cancelled")}>{u.is_active ? "active" : "inactive"}</span>
      </ResultRow>
    ));
  }
  if (tool === "get_chat_audit" && data.entries) {
    return data.entries.map((a, i) => (
      <div key={i} className="chat-journey-row">
        <div className="chat-journey-main">
          <strong>{a.tool} · {a.event}</strong>
          <span className="chat-muted">{fmtDate(a.created_at)}{a.detail ? ` · ${a.detail}` : ""}</span>
        </div>
        <span className={chipClass(a.permission_result === "denied" ? "blocked" : "active")}>{a.permission_result}</span>
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
  if (args.user_id) return `user ${String(args.user_id).slice(0, 8)}`;
  if (args.exception_id) return `exception ${String(args.exception_id).slice(0, 8)}`;
  return "";
}

/**
 * One chat bubble. For assistant messages carrying a pending_action, renders
 * the inline Confirm/Reject card; once resolved, shows the outcome state.
 */
export default function ChatMessageItem({ message, user, onNavigate, busy, onConfirm, onReject }) {
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
  const denied = Boolean(meta.permission_denied);
  const needsInfo = Boolean(meta.needs_info);
  const bubbleClass = `chat-bubble chat-bubble--assistant${denied ? " chat-bubble--denied" : ""}${needsInfo ? " chat-bubble--ask" : ""}`;

  return (
    <div className="chat-row chat-row--assistant">
      <div className="chat-avatar"><Wrench size={13} /></div>
      <div className="chat-bubble-group">
        {showText && <div className={bubbleClass}>
          {denied && <Ban size={12} className="chat-bubble-icon" aria-hidden />}
          <ChatMarkdown>{presentation.text}</ChatMarkdown>
        </div>}

        {showStructured && <div className="chat-data-card">
          <div className="chat-data-label"><Wrench size={11} /> {humanizeTool(presentation.result.tool)}</div>
          <StructuredData tool={presentation.result.tool} data={presentation.result.result.data} user={user} onNavigate={onNavigate} />
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
                <JourneyRow journey={actionResult.result.data.journey} user={user} onNavigate={onNavigate} />
              </div>
            )}
            {(actionResult.result?.summary || actionResult.error || message.content) && (
              <div className={`chat-action-outcome ${actionResult.status !== "executed" ? "chat-action-outcome--error" : ""}`}>
                <ChatMarkdown>{actionResult.status === "executed" ? actionResult.result?.summary || message.content : actionResult.error || message.content}</ChatMarkdown>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

import React from "react";
import { AlertTriangle, ArrowRight, Bot, Cog, Info, ShieldAlert, Sparkles } from "lucide-react";
import { humanize } from "../utils";
import Badge from "./Badge";

const componentName = value => humanize(String(value || "").replace(/([a-z])([A-Z])/g, "$1 $2"));

const FINAL_STATES = {
  WAIT: "Waiting - nothing more to do right now",
  ESCALATE: "Escalated to staff",
  FAILED: "Failed",
};
export const finalStateLabel = state => FINAL_STATES[String(state || "").toUpperCase()] || humanize(state);

const ACTION_LABELS = {
  SEND_REMINDER: "Reminder sent",
  REQUEST_DOCUMENT: "Document requested",
  REQUEST_APPOINTMENT: "Appointment requested",
  RESCHEDULE_APPOINTMENT: "Reschedule requested",
  CREATE_COORDINATOR_TASK: "Coordinator task",
};

function JsonDetails({ title, value, defaultOpen = false }) {
  if (value == null || (Array.isArray(value) && !value.length)) return null;
  return <details className="run-json" open={defaultOpen || undefined}><summary>{title}</summary><pre>{JSON.stringify(value, null, 2)}</pre></details>;
}

function StepChanges({ changes }) {
  return <div className="run-section">
    <h4>Steps changed by this run</h4>
    {changes.length ? <ul className="run-changes">{changes.map(c => <li key={c.step_id}>
      <div className="run-change-main">
        <strong>{c.step_name}</strong>
        <span className="run-change-flow"><Badge value={c.from} /><ArrowRight size={12} /><Badge value={c.to} /></span>
      </div>
      <small>
        <span className={`run-actor run-actor--${c.changed_by === "rules" ? "rules" : "agent"}`}>
          {c.changed_by === "rules" ? <><Cog size={10} /> Rule engine</> : <><Bot size={10} /> Agent action</>}
        </span>
        {c.reason}
      </small>
    </li>)}</ul> : <p className="run-empty">No step status changed.</p>}
  </div>;
}

function ActionOutcome({ item }) {
  const a = item.output || {};
  const label = ACTION_LABELS[a.action_type] || humanize(a.action_type);
  const tone = a.awaiting_approval ? "warn" : a.status === "FAILED" ? "bad" : "ok";
  return <div className={`run-outcome run-outcome--${tone}`}>
    <div className="run-outcome-head">
      <strong>{label}{a.step_name ? ` - ${a.step_name}` : ""}</strong>
      <span className="run-outcome-tag">
        {a.awaiting_approval ? "Waiting for staff approval" : a.status === "FAILED" ? "Failed" : a.duplicate ? "Already sent earlier" : a.delivery === "mock" ? "Simulated (email not configured)" : a.delivery === "in_app" ? "Task created" : "Sent and verified"}
      </span>
    </div>
    {a.reason && <p>Why: {a.reason}</p>}
    {a.awaiting_approval && <p className="run-note">Approve or reject it under "Journey actions" on this page.</p>}
    {a.step_completion_note && <p className="run-note">{a.step_completed ? "Step completed. " : "Step not changed. "}{a.step_completion_note}</p>}
    {a.error && <p className="form-error">{a.error}</p>}
    <JsonDetails title="Execution response" value={a.response} />
  </div>;
}

function Assessment({ output }) {
  return <div className="run-outcome">
    <div className="run-outcome-head"><strong>Journey assessment</strong>
      {output.confidence != null && <span className="run-outcome-tag">{Math.round(output.confidence * 100)}% confident</span>}
    </div>
    {output.assessment && <p>{output.assessment}</p>}
    {output.reason && <p>Why: {output.reason}</p>}
    {output.missing_prerequisites?.length > 0 && <p>Missing: {output.missing_prerequisites.join(", ")}</p>}
    {output.contradictory_evidence?.length > 0 && <p>Conflicting evidence: {output.contradictory_evidence.join(", ")}</p>}
  </div>;
}

function traceText(call) {
  if (call.operation === "ai_unavailable") return `AI unavailable (${call.reason}) - using rules`;
  if (call.operation) return humanize(call.operation);
  if (call.decision?.next_capability) {
    const who = call.decision.source === "rules" ? "Rules chose" : "Chose";
    return `${who} ${humanize(call.decision.next_capability)}${call.decision.target_step_name ? ` for "${call.decision.target_step_name}"` : ""}`;
  }
  if (call.component === "action_executor" && call.output?.action_type) return `Executed ${humanize(call.output.action_type)}`;
  if (call.output?.action_type) return `Suggested ${humanize(call.output.action_type)}`;
  if (call.output?.assessment) return "Assessed the journey";
  if (call.outcome) return `${humanize(call.outcome)}${call.exception_created ? " - exception opened" : ""}`;
  return "Returned output";
}

/** Works with the live POST response and the saved orchestration audit record. */
export default function AgentRunDetails({ run }) {
  const saved = run.run_type === "ORCHESTRATION";

  // Single agent records (supervisor / coordination / journey intelligence, or older runs).
  if (!saved && !run.calls) {
    const out = run.output || {};
    return <div className="run-detail-body">
      {run.error_message && <p className="run-warning"><AlertTriangle size={13} /> {run.error_message}</p>}
      {out.reason && <p className="run-reason">{out.reason}</p>}
      {out.next_capability && <p><b>Direction:</b> {humanize(out.next_capability)}{out.target_step_name ? ` - ${out.target_step_name}` : ""}</p>}
      {out.action_type && <p><b>Suggested action:</b> {humanize(out.action_type)}</p>}
      {out.assessment && <p><b>Assessment:</b> {out.assessment}</p>}
      <JsonDetails title="Full agent output" value={run.output} />
      <JsonDetails title="Input context" value={run.input_context} />
    </div>;
  }

  const output = saved ? run.output || {} : run;
  const decision = output.decision;
  const outcomes = output.outcomes || [];
  const calls = saved ? run.tool_calls || [] : run.calls || [];
  const failed = run.status === "FAILED";
  const finalState = failed ? "FAILED" : (saved ? output.final_state : run.status);
  const actions = outcomes.filter(o => o.component === "action_executor");
  const assessments = outcomes.filter(o => o.output?.assessment);
  const changes = output.step_changes || [];
  const rulesOnly = output.mode === "RULES_ONLY";

  return <div className="run-detail-body">
    <div className="run-summary">
      <span><b>Result</b>{finalStateLabel(finalState)}</span>
      {!failed && <span><b>Decided by</b>{rulesOnly ? "Built-in rules (AI not used)" : "AI agents + rules"}</span>}
      {output.journey_status && output.journey_status.from !== output.journey_status.to &&
        <span><b>Journey status</b>{humanize(output.journey_status.from)} <ArrowRight size={11} /> {humanize(output.journey_status.to)}</span>}
    </div>

    {failed && <p className="run-warning"><ShieldAlert size={14} /> {run.error_message || output.summary || "This run could not finish."}</p>}
    {!failed && output.summary && <p className="run-headline"><Sparkles size={14} /> {output.summary}</p>}
    {rulesOnly && output.warnings?.length > 0 && <p className="run-warning"><Info size={13} /> {output.warnings.join("; ")}</p>}

    {!failed && <>
      <StepChanges changes={changes} />
      <div className="run-section">
        <h4>Actions taken</h4>
        {actions.length ? actions.map((item, i) => <ActionOutcome key={i} item={item} />)
          : <p className="run-empty">No action was sent in this run.{decision?.reason ? ` ${decision.reason}` : ""}</p>}
      </div>
      {assessments.length > 0 && <div className="run-section"><h4>Agent assessment</h4>{assessments.map((item, i) => <Assessment key={i} output={item.output} />)}</div>}
      {finalState === "ESCALATE" && <p className="run-warning"><AlertTriangle size={13} /> An exception was opened for staff on the Exceptions page.</p>}
    </>}

    {calls.length > 0 && <details className="run-json"><summary>How the run proceeded ({calls.length} steps)</summary>
      <ol className="run-trace-list">{calls.map((call, index) => <li key={index}>
        <strong>{componentName(call.component)}</strong>
        <span>{traceText(call)}</span>
        {call.reason && call.operation !== "ai_unavailable" && <small>{call.reason}</small>}
      </li>)}</ol>
    </details>}
    <JsonDetails title="Technical details (JSON)" value={{ decision, result: output.result, calls }} />
    {saved && <JsonDetails title="Input context" value={run.input_context} />}
    <p className="run-boundary">Operational support only. Patient messages are emailed when SMTP is configured, otherwise simulated; staff should verify follow-up.</p>
  </div>;
}

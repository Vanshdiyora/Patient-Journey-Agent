import React from "react";
import { AlertTriangle, Ban, Check, Loader2, Wrench } from "lucide-react";

const ROLE_LABELS = {
  submit_event: "Record an update",
  orchestrate_journey: "Re-evaluate journey",
  list_journeys: "Look up journeys",
  get_journey_steps: "Look up journey steps",
};

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

  return (
    <div className="chat-row chat-row--assistant">
      <div className="chat-avatar"><Wrench size={13} /></div>
      <div className="chat-bubble-group">
        <div className="chat-bubble chat-bubble--assistant">
          {message.content}
          {busy && <span className="chat-typing-dots" aria-label="Assistant is typing"><i /><i /><i /></span>}
        </div>

        {pending && (
          <div className={`chat-action-card chat-action-card--${pending.status}`}>
            <div className="chat-action-head">
              <Wrench size={14} />
              <strong>{humanizeTool(pending.name)}</strong>
              {pending.status === "pending" && <span className="chat-action-badge">Awaiting confirmation</span>}
              {pending.status === "executed" && <span className="chat-action-badge chat-action-badge--done"><Check size={11} /> Done</span>}
              {pending.status === "failed" && <span className="chat-action-badge chat-action-badge--fail"><AlertTriangle size={11} /> Failed</span>}
              {pending.status === "rejected" && <span className="chat-action-badge chat-action-badge--muted"><Ban size={11} /> Rejected</span>}
            </div>
            {prettyArgs(pending.arguments) && (
              <div className="chat-action-args">{prettyArgs(pending.arguments)}</div>
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
            ) : (
              (pending.result?.summary || pending.error) && (
                <div className={`chat-action-outcome ${pending.status === "failed" ? "chat-action-outcome--error" : ""}`}>
                  {pending.status === "executed" ? pending.result?.summary : pending.error}
                </div>
              )
            )}
          </div>
        )}

        {!pending && actionResult && (
          <div className={`chat-action-card chat-action-card--${actionResult.status}`}>
            <div className="chat-action-head">
              <Wrench size={14} />
              <strong>{humanizeTool(actionResult.tool)}</strong>
              <span className={`chat-action-badge ${actionResult.status === "executed" ? "chat-action-badge--done" : "chat-action-badge--fail"}`}>
                {actionResult.status === "executed" ? <><Check size={11} /> Completed</> : <><AlertTriangle size={11} /> Failed</>}
              </span>
            </div>
            {(actionResult.result?.summary || actionResult.error) && (
              <div className={`chat-action-outcome ${actionResult.status !== "executed" ? "chat-action-outcome--error" : ""}`}>
                {actionResult.status === "executed" ? actionResult.result?.summary : actionResult.error}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

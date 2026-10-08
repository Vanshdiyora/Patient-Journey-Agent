import React, { useState } from "react";
import { Bot, CalendarClock, ChevronDown, ChevronRight, FileJson, Sparkles } from "lucide-react";
import { journeysApi } from "../../services";
import { useAsync } from "../../hooks/useAsync";
import { formatDate, humanize } from "../../utils";
import { JsonView, Panel, EmptyState, ErrorState, SkeletonRows, Badge } from "../../components";
import AgentRunDetails from "../../components/AgentRunDetails";
import AddEventForm from "./AddEventForm";

export function ContextPanel({ journeyId }) {
  const { data, loading } = useAsync(() => journeysApi.context(journeyId), [journeyId]);
  return <Panel title="Orchestration context" subtitle="Decision context" headerIcon={FileJson}>
    {loading ? <div className="mini-loader" /> : <JsonView data={data} />}
  </Panel>;
}

export function EventsPanel({ eventRows, loading, busy, onAdd }) {
  return <Panel title="Events" subtitle="Journey event stream" headerIcon={CalendarClock}>
    {loading ? <SkeletonRows count={4} /> : eventRows.length ? <div className="event-list">{eventRows.slice(0, 10).map(e =>
      <div className="event-row" key={e.id}>
        <div>
          <strong>{humanize(e.event_type)}</strong>
          <span>{e.source} · {formatDate(e.event_time, true)}</span>
          {e.payload?.comment && <span>{e.payload.comment}</span>}
        </div>
        <span className={`event-dot ${e.processed ? "event-dot--done" : ""}`} />
      </div>
    )}</div> : <EmptyState small title="No events" />}
    <AddEventForm busy={busy === "event"} onAdd={onAdd} />
  </Panel>;
}

export function AgentActivityPanel({ agentRows, loading, error }) {
  const [expanded, setExpanded] = useState(null);
  return <Panel title="Agent activity" subtitle="Latest agent runs for this journey" headerIcon={Bot}>
    {error ? <ErrorState error={error} title="Could not load agent activity" /> : loading ? <SkeletonRows count={3} /> : agentRows.length ?
      <div className="journey-run-list">{agentRows.slice(0, 8).map(a => <div className="journey-run" key={a.id}>
        <button className="journey-run-head" type="button" aria-expanded={expanded === a.id} onClick={() => setExpanded(expanded === a.id ? null : a.id)}>
          <Bot size={16} />
          <span><strong>{humanize(a.agent_name)}</strong><small>{formatDate(a.started_at, true)}</small></span>
          <Badge value={a.status} />
          {expanded === a.id ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
        </button>
        {expanded === a.id && <AgentRunDetails run={a} />}
      </div>)}</div> : <EmptyState small title="No agent runs" />}
    {agentRows.length > 8 && <p className="run-boundary">Showing 8 of {agentRows.length} recent records.</p>}
  </Panel>;
}

export function ActionsPanel({ actionRows, loading, error, busy, onDecide }) {
  return <Panel title="Journey actions" subtitle="Recorded action executions for this journey" headerIcon={Sparkles}>
    {error ? <ErrorState error={error} title="Could not load journey actions" /> : loading ? <SkeletonRows count={3} /> : actionRows.length ? <div className="journey-actions">{actionRows.map(a => <div className="journey-action" key={a.id}>
      <div className="journey-action-head"><Sparkles size={15} /><span><strong>{humanize(a.action_type)}</strong><small>{formatDate(a.requested_at, true)}</small></span><Badge value={a.status} fallback={a.status === "REQUESTED" ? "Awaiting approval" : undefined} /></div>
      {a.status === "REQUESTED" && <div className="journey-action-approval">
        <p>{a.response_payload?.reason || "Needs staff approval before it can run."}</p>
        {onDecide && <div className="journey-action-buttons">
          <button className="primary-btn" disabled={!!busy} onClick={() => onDecide(a, true)}>{busy === `action-${a.id}` ? "Working…" : "Approve"}</button>
          <button className="secondary-btn" disabled={!!busy} onClick={() => onDecide(a, false)}>Reject</button>
        </div>}
      </div>}
      {a.response_payload?.delivery && a.status === "SUCCESS" && <small className="journey-action-delivery">
        {a.response_payload.delivery === "email" ? "Delivered by email" : a.response_payload.delivery === "in_app" ? "Created as an in-app task" : "Simulated - email is not configured"}
      </small>}
      {a.response_payload && <details className="run-json"><summary>Execution response</summary><pre>{JSON.stringify(a.response_payload, null, 2)}</pre></details>}
      {a.error_message && <p className="form-error">{a.error_message}</p>}
    </div>)}</div> : <EmptyState small title="No actions recorded" text="Orchestration may decide to wait or escalate without executing an action." />}
    <p className="run-boundary">Reminders and requests are emailed to patients when SMTP is configured; otherwise they are simulated and labelled as such.</p>
  </Panel>;
}

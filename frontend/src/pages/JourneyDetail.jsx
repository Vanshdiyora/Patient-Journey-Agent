import React, { useState } from "react";
import {
  Activity, AlertTriangle, ArrowLeft, Bot, CalendarClock, CheckCircle2,
  Clock3, FileJson, Play, RefreshCw, Send, Sparkles
} from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { journeysApi, agentsApi } from "../services/api";
import { useAsync } from "../hooks/useAsync";
import { canViewObservability } from "../utils/roles";
import { useAuth } from "../context/AuthContext";
import { formatDate, getErrorMessage, humanize, shortId, toList } from "../utils/constants";
import { PageHeading, Panel, EmptyState, ErrorState, Badge, AlertBanner, JsonView, DetailSkeleton } from "../components";

const COMPLETED_STATES = ["completed", "resolved"];

function JourneyProgress({ steps }) {
  const done = steps.filter(s => COMPLETED_STATES.includes(String(s.status).toLowerCase())).length;
  const pct = steps.length ? Math.round((done / steps.length) * 100) : 0;
  return (
    <div className="journey-progress">
      <div className="journey-progress-head"><span>Journey progress</span><strong>{done} / {steps.length} steps completed</strong></div>
      <div className="progress-track"><div className="progress-value" style={{ width: `${pct}%` }} /></div>
    </div>
  );
}

function StepsTimeline({ steps }) {
  if (!steps.length) return <EmptyState small title="No steps returned" />;
  return (
    <div className="timeline">{steps.map((s, i) => (
      <div className={`timeline-item ${String(s.status).toLowerCase()}`} key={s.id}>
        <div className="timeline-marker">
          {COMPLETED_STATES.includes(String(s.status).toLowerCase()) ? <CheckCircle2 size={17} /> : i === 0 ? <Play size={15} /> : <Clock3 size={16} />}
        </div>
        <div className="timeline-content">
          <div className="timeline-top"><strong>Step {i + 1}</strong><Badge kind="status" value={s.status} /></div>
          <span className="timeline-sub">{s.pathway_step_id}</span>
          {s.block_reason && <div className="block-note"><AlertTriangle size={14} />{s.block_reason}</div>}
          <div className="timeline-dates">
            {s.started_at && <span>Started {formatDate(s.started_at, true)}</span>}
            {s.due_at && <span>Due {formatDate(s.due_at, true)}</span>}
          </div>
        </div>
      </div>
    ))}</div>
  );
}

function CompactList({ rows, icon: RowIcon, renderMain }) {
  if (!rows.length) return null;
  return (
    <div className="compact-list">{rows.map((a, i) => (
      <div className="compact-row" key={a.id || a.name || i}>
        <div className="compact-icon"><RowIcon size={15} /></div>
        <div>{renderMain(a, i)}</div>
      </div>
    ))}</div>
  );
}

function AddEventForm({ busy, onAdd }) {
  const [eventType, setEventType] = useState("");
  const [eventSource, setEventSource] = useState("carepath-ui");
  const [eventPayload, setEventPayload] = useState("{}");

  const submit = async (e) => {
    e.preventDefault();
    let payload = {};
    try { payload = JSON.parse(eventPayload || "{}"); }
    catch { alert("Event payload must be valid JSON."); return; }
    await onAdd({ event_type: eventType.trim(), source: eventSource.trim(), event_time: new Date().toISOString(), payload });
    setEventType("");
    setEventPayload("{}");
  };

  return (
    <form className="event-form" onSubmit={submit}>
      <div className="event-form-title"><Send size={14} /> Add event</div>
      <div className="event-form-grid">
        <input required value={eventType} onChange={e => setEventType(e.target.value)} placeholder="Event type" />
        <input required value={eventSource} onChange={e => setEventSource(e.target.value)} placeholder="Source" />
      </div>
      <textarea value={eventPayload} onChange={e => setEventPayload(e.target.value)} rows="4" spellCheck="false" placeholder='{"key":"value"}' />
      <button className="primary-btn" disabled={busy}>{busy ? "Adding…" : "Add event"}</button>
    </form>
  );
}

function ContextPanel({ journeyId }) {
  const { data, loading } = useAsync(() => journeysApi.context(journeyId), [journeyId]);
  if (loading) return <div className="mini-loader" />;
  return <JsonView data={data} />;
}

export default function JourneyDetail() {
  const { journeyId } = useParams();
  const journey = useAsync(() => journeysApi.get(journeyId), [journeyId]);
  const steps = useAsync(() => journeysApi.steps(journeyId), [journeyId]);
  const events = useAsync(() => journeysApi.events(journeyId, { limit: 100 }), [journeyId]);
  const actions = useAsync(() => journeysApi.actions(journeyId), [journeyId]);
  const agents = useAsync(() => agentsApi.runs({ journey_id: journeyId, limit: 20 }), [journeyId]);

  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const { user } = useAuth();
  const observability = canViewObservability(user);

  if (journey.loading) return <DetailSkeleton />;
  if (journey.error) return <ErrorState error={journey.error} title="Could not load journey" />;

  const j = journey.data;
  const stepRows = toList(steps.data);
  const eventRows = toList(events.data);
  const actionRows = toList(actions.data, "items", "actions");
  const agentRows = toList(agents.data);

  const run = async (type, fn) => {
    setBusy(type);
    setMessage("");
    try {
      await fn();
      setMessage(type === "orchestrate" ? "Orchestration completed." : "Evaluation completed.");
      await journey.refetch();
      await steps.refetch();
    } catch (e) {
      setMessage(getErrorMessage(e));
    } finally {
      setBusy("");
    }
  };

  const addEvent = async (payload) => {
    setBusy("event");
    setMessage("");
    try {
      await journeysApi.addEvent(journeyId, payload);
      setMessage("Event added successfully.");
      await events.refetch();
    } catch (err) {
      setMessage(getErrorMessage(err));
    } finally {
      setBusy("");
    }
  };

  return <div>
    <Link className="back-link" to="/journeys"><ArrowLeft size={16} /> Back to journeys</Link>
    <PageHeading
      eyebrow="Journey execution"
      title={shortId(j.id, 12)}
      description={undefined}
      actions={<>
        <button className="secondary-btn" disabled={!!busy} onClick={() => run("evaluate", () => journeysApi.evaluate(j.id))}>
          <RefreshCw size={16} />{busy === "evaluate" ? "Evaluating…" : "Evaluate"}
        </button>
        <button className="primary-btn" disabled={!!busy} onClick={() => run("orchestrate", () => journeysApi.orchestrate(j.id))}>
          <Play size={16} />{busy === "orchestrate" ? "Orchestrating…" : "Orchestrate"}
        </button>
      </>}
    />
    <div className="heading-meta" style={{ marginTop: -14, marginBottom: 16 }}>
      <Badge kind="status" value={j.status} />
      <Badge kind="priority" value={j.priority} />
      <span>Started {formatDate(j.started_at, true)}</span>
    </div>
    {message && <AlertBanner tone={message.includes("completed") ? "success" : "error"}>{message}</AlertBanner>}

    <JourneyProgress steps={stepRows} />

    <div className="content-grid content-grid--journey">
      <Panel wide title="Journey steps" subtitle="Current pathway state">
        <StepsTimeline steps={stepRows} />
      </Panel>

      {observability && <Panel title="Orchestration context" subtitle="Decisioning context" headerIcon={FileJson}>
        <ContextPanel journeyId={j.id} />
      </Panel>}

      {observability && <Panel title="Agent activity" subtitle="Latest agent runs for this journey" headerIcon={Bot}>
        {agentRows.length ? (
          <CompactList rows={agentRows.slice(0, 8)} icon={Bot} renderMain={(a) => (
            <><strong>{humanize(a.agent_name)}</strong><span>{humanize(a.run_type)} · {formatDate(a.started_at, true)}</span></>
          )} />
        ) : <EmptyState small title="No agent runs" />}
        {agentRows.length > 8 && <div className="panel-header" style={{ borderTop: "1px solid #edf0f0" }}><span style={{ fontSize: 10, color: "#84908e" }}>Showing 8 of {agentRows.length}</span></div>}
      </Panel>}

      <Panel title="Events" subtitle="Journey event stream" headerIcon={CalendarClock}>
        {eventRows.length ? (
          <div className="event-list">{eventRows.slice(0, 10).map(e => (
            <div className="event-row" key={e.id}>
              <div><strong>{humanize(e.event_type)}</strong><span>{e.source} · {formatDate(e.event_time, true)}</span></div>
              <span className={`event-dot ${e.processed ? "event-dot--done" : ""}`} />
            </div>
          ))}</div>
        ) : <EmptyState small title="No events" />}
        <AddEventForm busy={busy === "event"} onAdd={addEvent} />
      </Panel>

      <Panel title="Journey actions" subtitle="Actions available for this journey" headerIcon={Sparkles}>
        {actionRows.length ? (
          <CompactList rows={actionRows} icon={Sparkles} renderMain={(a, i) => (
            <><strong>{humanize(a.name || a.action_name || `Action ${i + 1}`)}</strong><span>{a.description || a.summary || "Available orchestration action"}</span></>
          )} />
        ) : <EmptyState small title="No journey actions" />}
      </Panel>
    </div>
  </div>;
}

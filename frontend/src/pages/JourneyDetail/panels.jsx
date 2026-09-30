import React from "react";
import { Bot, CalendarClock, FileJson, Sparkles } from "lucide-react";
import { journeysApi } from "../../services";
import { useAsync } from "../../hooks/useAsync";
import { formatDate, humanize, toList } from "../../utils";
import { canViewObservability } from "../../utils/roles";
import { JsonView, Panel, EmptyState, SkeletonRows } from "../../components";
import AddEventForm from "./AddEventForm";

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

/** Orchestration decision context (observability roles only). */
export function ContextPanel({ journeyId }) {
  const { data, loading } = useAsync(() => journeysApi.context(journeyId), [journeyId]);
  return (
    <Panel title="Orchestration context" subtitle="Decisioning context" headerIcon={FileJson}>
      {loading ? <div className="mini-loader" /> : <JsonView data={data} />}
    </Panel>
  );
}

/** Journey event stream + staff add-event form. */
export function EventsPanel({ journeyId, eventRows, loading, busy, onAdd }) {
  return (
    <Panel title="Events" subtitle="Journey event stream" headerIcon={CalendarClock}>
      {loading ? <SkeletonRows count={4} /> : eventRows.length ? (
        <div className="event-list">{eventRows.slice(0, 10).map(e => (
          <div className="event-row" key={e.id}>
            <div><strong>{humanize(e.event_type)}</strong><span>{e.source} · {formatDate(e.event_time, true)}</span></div>
            <span className={`event-dot ${e.processed ? "event-dot--done" : ""}`} />
          </div>
        ))}</div>
      ) : <EmptyState small title="No events" />}
      <AddEventForm busy={busy === "event"} onAdd={onAdd} />
    </Panel>
  );
}

/** Latest agent runs for this journey (observability roles only). */
export function AgentActivityPanel({ agentRows }) {
  return (
    <Panel title="Agent activity" subtitle="Latest agent runs for this journey" headerIcon={Bot}>
      {agentRows.length ? (
        <CompactList rows={agentRows.slice(0, 8)} icon={Bot} renderMain={(a) => (
          <><strong>{humanize(a.agent_name)}</strong><span>{humanize(a.run_type)} · {formatDate(a.started_at, true)}</span></>
        )} />
      ) : <EmptyState small title="No agent runs" />}
      {agentRows.length > 8 && <div className="panel-header" style={{ borderTop: "1px solid #edf0f0" }}><span style={{ fontSize: 10, color: "#84908e" }}>Showing 8 of {agentRows.length}</span></div>}
    </Panel>
  );
}

/** Actions executed/available for this journey. */
export function ActionsPanel({ actionRows }) {
  return (
    <Panel title="Journey actions" subtitle="Actions available for this journey" headerIcon={Sparkles}>
      {actionRows.length ? (
        <CompactList rows={actionRows} icon={Sparkles} renderMain={(a, i) => (
          <><strong>{humanize(a.name || a.action_name || `Action ${i + 1}`)}</strong><span>{a.description || a.summary || "Available orchestration action"}</span></>
        )} />
      ) : <EmptyState small title="No journey actions" />}
    </Panel>
  );
}

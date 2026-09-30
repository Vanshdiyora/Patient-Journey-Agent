import React, { useState } from "react";
import { Bot, ChevronDown, ChevronRight, Clock3, Code2, Terminal } from "lucide-react";
import { agentsApi } from "../services/api";
import { useAsync } from "../hooks/useAsync";
import { formatDate, formatDuration, humanize, toList } from "../utils/constants";
import { PageHeading, Panel, EmptyState, ErrorState, Badge, SkeletonRows } from "../components";

export default function AgentRuns() {
  const [expanded, setExpanded] = useState(null);
  const { data, loading, error } = useAsync(() => agentsApi.runs({ limit: 100 }), []);
  const rows = toList(data, "items", "runs");

  return <div>
    <PageHeading eyebrow="Agent observability" title="Agent activity" description="Audit agent execution, context, tool calls and outcomes." />
    <Panel
      title="Recent agent runs"
      subtitle={`${rows.length} execution records returned by the orchestration API`}
      action={
        <div className="agent-legend">
          <span><i className="legend-dot legend-dot--green" />Completed</span>
          <span><i className="legend-dot" />Other</span>
        </div>
      }
    >
      {error ? <ErrorState error={error} title="Could not load agent runs" /> :
        loading ? <SkeletonRows count={7} /> :
          rows.length ? (
            <div className="agent-run-list">{rows.map(r => (
              <div className="agent-run" key={r.id}>
                <button className="agent-run-head" onClick={() => setExpanded(expanded === r.id ? null : r.id)}>
                  <div className="agent-run-icon"><Bot size={18} /></div>
                  <div className="agent-run-title"><strong>{humanize(r.agent_name)}</strong><span>{humanize(r.run_type)} · {formatDate(r.started_at, true)}</span></div>
                  <Badge kind="status" value={r.status} />
                  <div className="agent-run-time"><Clock3 size={14} />{r.completed_at ? formatDuration(r.started_at, r.completed_at) : "Running"}</div>
                  {expanded === r.id ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                </button>
                {expanded === r.id && (
                  <div className="agent-run-detail">
                    <div><h4><Terminal size={15} /> Input context</h4><pre>{JSON.stringify(r.input_context || {}, null, 2)}</pre></div>
                    <div><h4><Code2 size={15} /> Output</h4><pre>{JSON.stringify(r.output || {}, null, 2)}</pre></div>
                    {r.tool_calls && <div><h4>Tool calls</h4><pre>{JSON.stringify(r.tool_calls, null, 2)}</pre></div>}
                    {r.error_message && <div className="form-error">{r.error_message}</div>}
                  </div>
                )}
              </div>
            ))}</div>
          ) : <EmptyState icon={Bot} title="No agent activity" text="Agent runs will appear here as journeys are evaluated and orchestrated." />}
    </Panel>
  </div>;
}

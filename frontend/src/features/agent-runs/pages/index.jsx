import React, { useEffect, useState } from "react";
import { Bot, ChevronDown, ChevronRight, Clock3 } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { agentsApi } from "../../../services/index";
import { useAsync } from "../../../hooks/useAsync";
import { formatDate, formatDuration, humanize, toList } from "../../../utils/index";
import { PageHeading, Panel, EmptyState, ErrorState, Badge, SkeletonRows, Pagination } from "../../../components/index";
import AgentRunDetails from "../../../components/AgentRunDetails";
import { PATHS, buildPath } from "../../../routes/paths";

export default function AgentRuns() {
  const [searchParams] = useSearchParams();
  const runId = searchParams.get("run");
  const [expanded, setExpanded] = useState(() => runId);
  const [offset, setOffset] = useState(0);
  useEffect(() => { setOffset(0); setExpanded(runId); }, [runId]);
  const { data, loading, error } = useAsync(() => agentsApi.runs({ limit: 10, offset, run_id: runId || undefined }), [offset, runId]);
  const rows = toList(data, "items", "runs");
  const selected = expanded;

  return <div>
    <PageHeading eyebrow="Agent observability" title="Agent activity" description="Audit agent execution, context, tool calls and outcomes." />
    <Panel
      title="Recent agent runs"
      subtitle={`${data?.total ?? rows.length} saved agent and orchestration records`}
      action={
        <div className="agent-legend">
          {runId && <Link className="text-link" to={PATHS.agentRuns}>All runs</Link>}
          <span>Open a run to inspect its output and steps</span>
        </div>
      }
    >
      {error ? <ErrorState error={error} title="Could not load agent runs" /> :
        loading ? <SkeletonRows count={7} /> :
          rows.length ? (
            <div className="agent-run-list">{rows.map(r => (
              <div className="agent-run" key={r.id}>
                <button className="agent-run-head" aria-expanded={selected === r.id} onClick={() => setExpanded(selected === r.id ? null : r.id)}>
                  <div className="agent-run-icon"><Bot size={18} /></div>
                  <div className="agent-run-title"><strong>{humanize(r.agent_name)}</strong><span>{humanize(r.run_type)} · {formatDate(r.started_at, true)}</span></div>
                  <Badge kind="status" value={r.status} />
                  <div className="agent-run-time"><Clock3 size={14} />{r.completed_at ? formatDuration(r.started_at, r.completed_at) : "Running"}</div>
                  {selected === r.id ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                </button>
                {selected === r.id && (
                  <div className="agent-run-detail">
                    <div className="run-detail-main">
                      <Link className="text-link" to={buildPath(PATHS.journeyDetail, { journeyId: r.journey_id })}>Open journey</Link>
                      <AgentRunDetails run={r} />
                    </div>
                  </div>
                )}
              </div>
            ))}</div>
          ) : <EmptyState icon={Bot} title="No agent activity" text="Agent runs will appear here as journeys are evaluated and orchestrated." />}
      {!loading && !error && <Pagination offset={offset} count={rows.length} total={data?.total ?? 0} onPage={setOffset} />}
    </Panel>
  </div>;
}

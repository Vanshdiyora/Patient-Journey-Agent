import React from "react";
import { Activity, ChevronRight, CircleCheck, Zap } from "lucide-react";
import { actionsApi } from "../services";
import { useAsync } from "../hooks/useAsync";
import { humanize, toList } from "../utils";
import { PageHeading, Panel, EmptyState, ErrorState, SkeletonRows } from "../components";

export default function ActionRegistry() {
  const { data, loading, error } = useAsync(() => actionsApi.registry(), []);
  const rows = toList(data, "items", "actions", "registry");

  return <div>
    <PageHeading eyebrow="Automation catalog" title="Action registry" description="Available actions that the orchestration layer can invoke." />
    <Panel>
      {error ? <ErrorState error={error} title="Could not load action registry" /> :
        loading ? <SkeletonRows count={5} /> :
          rows.length ? (
            <div className="action-grid">{rows.map((a, i) => (
              <div className="action-card" key={a.id || a.name || i}>
                <div className="action-icon"><Zap size={19} /></div>
                <div className="action-copy">
                  <h3>{humanize(a.name || a.action_name || `Action ${i + 1}`)}</h3>
                  <p>{a.description || a.summary || "Registered orchestration action."}</p>
                  <div className="action-meta">
                    <span><CircleCheck size={14} /> Available</span>
                    {a.method && <code>{a.method}</code>}
                    {a.endpoint && <code>{a.endpoint}</code>}
                  </div>
                </div>
                <ChevronRight size={18} />
              </div>
            ))}</div>
          ) : <EmptyState icon={Activity} title="No actions registered" text="The backend action registry returned no actions." />}
    </Panel>
  </div>;
}

import React, { useState } from "react";
import { Network } from "lucide-react";
import { Link } from "react-router-dom";
import { journeysApi } from "../services/api";
import { useAsync } from "../hooks/useAsync";
import { formatDate, toList } from "../utils/constants";
import { PageHeading, Panel, EmptyState, ErrorState, Badge, Pagination, FilterSelect, ResultCount, SkeletonRows } from "../components";

const STATUS_OPTIONS = [
  { value: "active", label: "Active" },
  { value: "in_progress", label: "In progress" },
  { value: "completed", label: "Completed" },
  { value: "blocked", label: "Blocked" },
];
const PRIORITY_OPTIONS = [
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "normal", label: "Normal" },
  { value: "low", label: "Low" },
];

export default function Journeys() {
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [offset, setOffset] = useState(0);
  const limit = 20;
  const { data, loading, error } = useAsync(
    () => journeysApi.list({ status: status || undefined, priority: priority || undefined, limit, offset }),
    [status, priority, offset]
  );
  const rows = toList(data, "items", "journeys");

  return <div>
    <PageHeading eyebrow="Pathway operations" title="Patient journeys" description="Track progress, priorities and pathway execution." />
    <Panel>
      <div className="toolbar">
        <div className="filter-group">
          <FilterSelect label="All statuses" value={status} onChange={v => { setStatus(v); setOffset(0); }} options={STATUS_OPTIONS} />
          <FilterSelect label="All priorities" value={priority} onChange={v => { setPriority(v); setOffset(0); }} options={PRIORITY_OPTIONS} />
        </div>
        <ResultCount icon={Network}>{rows.length} shown</ResultCount>
      </div>
      {error ? <ErrorState error={error} title="Could not load journeys" /> :
        loading ? <SkeletonRows /> :
          rows.length ? (
            <div className="table-wrap"><table>
              <thead><tr><th>Journey</th><th>Patient</th><th>Priority</th><th>Status</th><th>Started</th><th>Target completion</th></tr></thead>
              <tbody>{rows.map(j => (
                <tr key={j.id}>
                  <td><Link className="table-primary" to={`/journeys/${j.id}`}>#{String(j.id).slice(0, 8)}</Link><span className="table-secondary">{j.pathway_name || j.pathway_id || "Care pathway"}</span></td>
                  <td><Link className="table-link" to={`/patients/${j.patient_id}`}>{String(j.patient_id).slice(0, 8)}…</Link></td>
                  <td><Badge kind="priority" value={j.priority} /></td>
                  <td><Badge kind="status" value={j.status} /></td>
                  <td>{formatDate(j.started_at, true)}</td>
                  <td>{formatDate(j.target_completion_at, true)}</td>
                </tr>
              ))}</tbody>
            </table></div>
          ) : <EmptyState icon={Network} title="No journeys found" text="Change the filters to see other journeys." />}
      <Pagination offset={offset} limit={limit} count={rows.length} onPage={setOffset} />
    </Panel>
  </div>;
}

import React from "react";
import { Network } from "lucide-react";
import { Link } from "react-router-dom";
import { formatDate, humanize } from "../../../utils/index";
import { Badge, Panel, EmptyState, SkeletonRows } from "../../../components/index";

/** Recent patient journeys table on the staff dashboard. */
export default function RecentJourneys({ loading, recent, scope }) {
  return (
    <Panel wide title="Recent patient journeys" subtitle={scope === "assigned" ? "Within your assigned scope" : "Latest pathway activity"}
      action={<Link className="text-link" to="/journeys">View all</Link>}>
      {loading ? <SkeletonRows count={5} /> : recent.length ? (
        <div className="table-wrap"><table>
          <thead><tr><th>Patient</th><th>Journey</th><th>Priority</th><th>Status</th><th>Updated</th></tr></thead>
          <tbody>{recent.slice(0, 7).map((j, i) => (
            <tr key={j.id || i}>
              <td><Link className="table-primary" to={`/patients/${j.patient_id}`}>{j.patient_name || j.patient_reference || `Patient ${String(j.patient_id || "").slice(0, 8)}`}</Link></td>
              <td>{humanize(j.pathway_name || j.pathway_id || "Care pathway")}</td>
              <td><Badge kind="priority" value={j.priority || "normal"} /></td>
              <td><Badge kind="status" value={j.status || "active"} /></td>
              <td>{formatDate(j.updated_at || j.created_at || j.started_at, true)}</td>
            </tr>
          ))}</tbody>
        </table></div>
      ) : <EmptyState icon={Network} title="No recent journeys" text="Journey activity will appear here when data is available." />}
    </Panel>
  );
}

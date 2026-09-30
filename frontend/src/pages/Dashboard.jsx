import React from "react";
import { AlertTriangle, CheckCircle2, Network, ShieldCheck, Users, Bot, Activity } from "lucide-react";
import { Link } from "react-router-dom";
import { dashboardApi, healthApi } from "../services/api";
import { useAsync } from "../hooks/useAsync";
import { formatDate, humanize, toList } from "../utils/constants";
import { PageHeading, Panel, EmptyState, Badge, MetricCard, SkeletonRows, AlertBanner } from "../components";

function Pulse({ icon: Icon, label, value }) {
  return <div className="pulse-row"><Icon size={17} /><span>{label}</span><b>{value}</b></div>;
}

export default function Dashboard() {
  const { data, loading, error, refetch } = useAsync(() => dashboardApi.summary(), []);
  const health = useAsync(() => healthApi.check(), []);

  const d = data || {};
  const stat = (keys, fallback = 0) => keys.reduce((v, k) => v ?? d?.[k], undefined) ?? fallback;
  const recent = toList(d.recent_journeys || d.recent);
  const exceptionCount = stat(["open_exceptions", "exceptions_open", "active_exceptions"]);
  const activeJourneys = stat(["active_journeys", "in_progress_journeys"]);
  const patientCount = stat(["patients", "patient_count", "total_patients"]);
  const completed = stat(["completed_journeys", "journeys_completed"]);

  return <div>
    <PageHeading
      eyebrow="Clinical command center"
      title="Good morning, care team."
      description="Monitor patient journeys, exceptions and orchestration activity from one place."
      actions={<button className="secondary-btn" onClick={() => refetch()}>Refresh</button>}
    />

    <section className="metric-grid">
      <MetricCard icon={Users} label="Patients" value={patientCount} hint="Across active pathways" tone="teal" />
      <MetricCard icon={Network} label="Active journeys" value={activeJourneys} hint="Currently in progress" tone="blue" />
      <MetricCard icon={AlertTriangle} label="Open exceptions" value={exceptionCount} hint="Need attention" tone="amber" />
      <MetricCard icon={CheckCircle2} label="Completed journeys" value={completed} hint="Recorded outcomes" tone="green" />
    </section>

    {error && <AlertBanner tone="error">
      <div><strong>Dashboard data unavailable</strong><span>Check that the API is running and accessible.</span></div>
      <button onClick={() => refetch()}>Retry</button>
    </AlertBanner>}

    <div className="content-grid content-grid--dashboard">
      <Panel wide title="Recent patient journeys" subtitle="Latest pathway activity"
        action={<Link className="text-link" to="/journeys">View all</Link>}>
        {loading ? <SkeletonRows count={5} /> : recent.length ? (
          <div className="table-wrap"><table>
            <thead><tr><th>Patient</th><th>Journey</th><th>Priority</th><th>Status</th><th>Updated</th></tr></thead>
            <tbody>{recent.slice(0, 7).map((j, i) => (
              <tr key={j.id || i}>
                <td><Link className="table-primary" to={`/patients/${j.patient_id}`}>{j.patient_reference || j.patient_name || `Patient ${String(j.patient_id || "").slice(0, 8)}`}</Link></td>
                <td>{humanize(j.pathway_name || j.pathway_id || "Care pathway")}</td>
                <td><Badge kind="priority" value={j.priority || "normal"} /></td>
                <td><Badge kind="status" value={j.status || "active"} /></td>
                <td>{formatDate(j.updated_at || j.created_at || j.started_at, true)}</td>
              </tr>
            ))}</tbody>
          </table></div>
        ) : <EmptyState icon={Network} title="No recent journeys" text="Journey activity will appear here when data is available." />}
      </Panel>

      <Panel title="System pulse" subtitle="Service availability">
        <div className="pulse-card">
          <span className={`pulse-dot ${health.loading ? "pulse-dot--loading" : ""}`} />
          <div><strong>{health.error ? "API unavailable" : "API operational"}</strong><span>{health.error ? "Unable to reach health endpoint" : "All core services responding"}</span></div>
        </div>
        <div className="pulse-list">
          <Pulse icon={ShieldCheck} label="Authentication" value="Protected" />
          <Pulse icon={Bot} label="Orchestration" value="Ready" />
          <Pulse icon={Activity} label="Agent runtime" value="Connected" />
        </div>
      </Panel>
    </div>
  </div>;
}

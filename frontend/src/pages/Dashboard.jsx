import React from "react";
import {
  AlertTriangle, Bot, CheckCircle2, Clock3, Network, RefreshCw,
  ShieldCheck, UserCog, Users, Zap, HeartPulse, Activity
} from "lucide-react";
import { Link } from "react-router-dom";
import { dashboardApi, healthApi } from "../services/api";
import { useAsync } from "../hooks/useAsync";
import { useAuth } from "../context/AuthContext";
import { formatDate, humanize, toList } from "../utils/constants";
import { isAdmin, isCoordinator, portalName } from "../utils/roles";
import { PageHeading, Panel, EmptyState, Badge, MetricCard, SkeletonRows, AlertBanner } from "../components";

function Pulse({ icon: Icon, label, value }) {
  return <div className="pulse-row"><Icon size={17} /><span>{label}</span><b>{value}</b></div>;
}

/** Role-specific metric configuration. Each portal sees its own KPIs. */
function metricsFor(user, d) {
  const admin = isAdmin(user);
  const cards = [
    // Shared operational metrics (all staff)
    { icon: Users, label: admin ? "Total patients" : "My patients", value: d.total_patients, hint: admin ? "Registered in the system" : "In your care scope", tone: "teal" },
    { icon: Network, label: "Active journeys", value: d.active_journeys, hint: "Currently in progress", tone: "blue" },
  ];

  if (admin) {
    cards.push(
      { icon: AlertTriangle, label: "Open exceptions", value: d.open_exceptions, hint: `${d.critical_exceptions || 0} critical`, tone: "amber" },
      { icon: UserCog, label: "Platform users", value: d.total_users, hint: `${d.active_users || 0} active · ${d.patient_users || 0} patient logins`, tone: "purple" },
    );
  } else if (isCoordinator(user)) {
    cards.push(
      { icon: AlertTriangle, label: "Follow-ups needed", value: d.open_exceptions, hint: `${d.critical_exceptions || 0} critical`, tone: "amber" },
      { icon: Clock3, label: "Steps awaiting action", value: d.pending_steps, hint: "Pending, ready or in progress", tone: "green" },
    );
  } else {
    // Clinician
    cards.push(
      { icon: AlertTriangle, label: "Clinical exceptions", value: d.open_exceptions, hint: `${d.critical_exceptions || 0} critical`, tone: "amber" },
      { icon: CheckCircle2, label: "Completed journeys", value: d.completed_journeys, hint: "Recorded outcomes", tone: "green" },
    );
  }
  return cards;
}

export default function Dashboard() {
  const { user } = useAuth();
  const { data, loading, error, refetch } = useAsync(() => dashboardApi.summary(), []);
  const health = useAsync(() => healthApi.check(), []);

  const d = data || {};
  const recent = toList(d.recent_journeys || d.recent);
  const admin = isAdmin(user);
  const coordinator = isCoordinator(user);

  return <div>
    <PageHeading
      eyebrow={portalName(user)}
      title={admin ? "Platform overview." : coordinator ? "Your coordination queue." : "Good day, doctor."}
      description={
        admin ? "System-wide activity, identities and orchestration health."
        : coordinator ? "Operational follow-ups, journey progress and task history at a glance."
        : "Clinical scope: patients, journey state and exceptions needing review."
      }
      actions={<button className="secondary-btn" onClick={() => refetch()}><RefreshCw size={16} /> Refresh</button>}
    />

    <section className="metric-grid">
      {(loading ? Array.from({ length: 4 }) : metricsFor(user, d)).map((m, i) =>
        m ? <MetricCard key={i} {...m} /> : <div className="metric-card" key={i} />
      )}
    </section>

    {error && <AlertBanner tone="error">
      <div><strong>Dashboard data unavailable</strong><span>Check that the API is running and accessible.</span></div>
      <button onClick={() => refetch()}>Retry</button>
    </AlertBanner>}

    <div className="content-grid content-grid--dashboard">
      <Panel wide title="Recent patient journeys" subtitle={d.scope === "assigned" ? "Within your assigned scope" : "Latest pathway activity"}
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
          <Pulse icon={ShieldCheck} label="Authentication" value="Email and password" />
          <Pulse icon={admin ? UserCog : Bot} label={admin ? "Identity store" : "Orchestration"} value={admin ? `${d.active_users ?? "—"} active` : "Ready"} />
          <Pulse icon={admin ? Activity : Zap} label={admin ? "Audit trail" : "Agent runtime"} value={admin ? "Recording" : "Connected"} />
        </div>
      </Panel>
    </div>
  </div>;
}

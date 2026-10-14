import React from "react";
import {
  AlertTriangle, CheckCircle2, Clock3, Network, RefreshCw, UserCog, Users,
} from "lucide-react";
import { dashboardApi, healthApi } from "../../services";
import { useAuth } from "../../context/AuthContext";
import { useAsync } from "../../hooks/useAsync";
import { toList } from "../../utils";
import { isAdmin, isCoordinator, portalName } from "../../utils/roles";
import { PageHeading, MetricCard, MetricCardSkeleton, AlertBanner } from "../../components";
import RecentJourneys from "./RecentJourneys";
import SystemPulse from "./SystemPulse";

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

    <section className="metric-grid" aria-label="Dashboard metrics" aria-busy={loading}>
      {loading
        ? Array.from({ length: 4 }, (_, i) => <MetricCardSkeleton key={i} />)
        : metricsFor(user, d).map((m, i) => <MetricCard key={i} {...m} />)}
    </section>

    {error && <AlertBanner tone="error">
      <div><strong>Dashboard data unavailable</strong><span>Check that the API is running and accessible.</span></div>
      <button onClick={() => refetch()}>Retry</button>
    </AlertBanner>}

    <div className="content-grid content-grid--dashboard">
      <RecentJourneys loading={loading} recent={recent} scope={d.scope} />
      <SystemPulse health={health} summary={d} isAdmin={admin} />
    </div>
  </div>;
}

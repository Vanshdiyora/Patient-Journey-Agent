import React from "react";
import { Activity, Bot, ShieldCheck, UserCog, Zap } from "lucide-react";
import { Panel } from "../../components";

function Pulse({ icon: Icon, label, value }) {
  return <div className="pulse-row"><Icon size={17} /><span>{label}</span><b>{value}</b></div>;
}

/** API availability card + role-flavored service list on the dashboard. */
export default function SystemPulse({ health, summary, isAdmin }) {
  const loading = health.loading;
  return (
    <Panel title="System pulse" subtitle="Service availability">
      <div className="pulse-card">
        <span className={`pulse-dot ${loading ? "pulse-dot--loading" : ""}`} />
        <div><strong>{health.error ? "API unavailable" : "API operational"}</strong><span>{health.error ? "Unable to reach health endpoint" : "All core services responding"}</span></div>
      </div>
      <div className="pulse-list">
        <Pulse icon={ShieldCheck} label="Authentication" value="Email and password" />
        <Pulse icon={isAdmin ? UserCog : Bot} label={isAdmin ? "Identity store" : "Orchestration"} value={isAdmin ? `${summary.active_users ?? "—"} active` : "Ready"} />
        <Pulse icon={isAdmin ? Activity : Zap} label={isAdmin ? "Audit trail" : "Agent runtime"} value={isAdmin ? "Recording" : "Connected"} />
      </div>
    </Panel>
  );
}

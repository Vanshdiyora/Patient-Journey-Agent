import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Activity, HeartPulse, ListChecks, Send } from "lucide-react";
import { meApi } from "../../../services/index";
import { useAsync } from "../../../hooks/useAsync";
import { useTabs } from "../../../hooks/useTabs";
import { formatDate, getErrorMessage, toList } from "../../../utils/index";
import { useAuth } from "../../../context/AuthContext";
import { Badge, EmptyState, Panel, TabBar, Pagination } from "../../../components/index";
import JourneyMetrics from "./JourneyMetrics";
import CarePlanPanel from "./CarePlanPanel";
import UpdatesPanel from "./UpdatesPanel";
import JourneyPicker from "./JourneyPicker";
import { EVENT_TYPES } from "./ReportForm";

/** Patient portal tabs. Data in every tab comes from /me/* — scoped to the
 * signed-in patient by the backend; no other patient's data is reachable. */
const TABS = [
  { id: "overview", label: "Overview", icon: Activity },
  { id: "plan", label: "Care plan", icon: ListChecks },
  { id: "updates", label: "My updates", icon: Send },
];

/** Shared page pieces rendered across tabs. */
function ProgressCard({ done, total }) {
  return (
    <div className="journey-progress">
      <div className="journey-progress-head"><span>Your progress</span><strong>{done} / {total} steps completed</strong></div>
      <div className="progress-track"><div className="progress-value" style={{ width: `${total ? Math.round(done / total * 100) : 0}%` }} /></div>
    </div>
  );
}

function UpdateTypesPanel() {
  return (
    <Panel title="Update types" subtitle="What you can send your care team">
      <div className="detail-list">
        {EVENT_TYPES.map(t => (
          <div className="detail-row" key={t.value}><span>{t.label}</span><strong style={{ fontSize: 9, color: "#899592" }}>Reviewed by care team</strong></div>
        ))}
      </div>
    </Panel>
  );
}

export default function MyJourney() {
  const { user } = useAuth();
  const { active: tab, select: setTab } = useTabs("overview");
  const [journeyOffset, setJourneyOffset] = useState(0);
  const [eventOffset, setEventOffset] = useState(0);
  const journeys = useAsync(() => meApi.journeys({ limit: 10, offset: journeyOffset }), [journeyOffset]);
  const rows = toList(journeys.data, "items");
  const [searchParams, setSearchParams] = useSearchParams();
  const linkedJourneyId = searchParams.get("journeyId");
  const currentId = rows.find(j => j.id === linkedJourneyId)?.id || rows[0]?.id || null;
  useEffect(() => {
    if (journeyOffset && journeys.data?.total != null && journeyOffset >= journeys.data.total) setJourneyOffset(Math.max(0, Math.ceil(journeys.data.total / 10) - 1) * 10);
  }, [journeys.data?.total, journeyOffset]);
  useEffect(() => { setEventOffset(0); }, [currentId]);
  const selectJourney = (id) => setSearchParams(current => {
    const next = new URLSearchParams(current);
    next.set("journeyId", id);
    return next;
  });
  const currentJourney = rows.find(j => j.id === currentId);
  const steps = useAsync(() => (currentId ? meApi.journeySteps(currentId) : Promise.resolve([])), [currentId]);
  const events = useAsync(() => (currentId ? meApi.journeyEvents(currentId, { limit: 10, offset: eventOffset }) : Promise.resolve({ items: [], total: 0 })), [currentId, eventOffset]);
  const stepRows = toList(steps.data);
  const eventRows = toList(events.data, "items");
  const done = stepRows.filter(s => ["COMPLETED", "RESOLVED"].includes(String(s.status).toUpperCase())).length;
  const submitStep = async (stepId, comment) => {
    await meApi.submitStep(currentId, stepId, comment);
    await Promise.all([steps.refetch(), events.refetch()]);
  };

  if (journeys.loading) return <div className="skeleton-detail"><i /><i /><i /></div>;
  if (journeys.error) return <div className="empty-state"><strong>Could not load your journey</strong><span>{getErrorMessage(journeys.error)}</span></div>;

  if (!rows.length && journeys.data?.total > 0) return <div className="skeleton-detail"><i /><i /><i /></div>;
  if (!rows.length) {
    return <EmptyState icon={HeartPulse} title="No active journey" text="Your care team has not started a journey for you yet." />;
  }

  const nextStep = stepRows.find(s => !["COMPLETED", "RESOLVED", "CANCELLED"].includes(String(s.status).toUpperCase()));

  return <div>
    <div className="page-heading">
      <div>
        <span className="eyebrow">My health</span>
        <h1>Hello, {user?.name || user?.email?.split("@")[0]}</h1>
        <p>Follow your care plan and send updates to your care team.</p>
      </div>
    </div>

    <div className="patient-journey-summary">
      <div><span className="eyebrow">Current care journey</span><strong>{currentJourney?.pathway_name || "Care journey"}</strong><small>Started {formatDate(currentJourney?.started_at)}</small></div>
      <Badge kind="status" value={currentJourney?.status} />
    </div>

    <TabBar
      tabs={TABS.map(t => ({
        ...t,
        count: t.id === "plan" ? stepRows.length : t.id === "updates" ? events.data?.total : undefined,
      }))}
      active={tab}
      onChange={setTab}
    />

    {tab === "overview" && <>
      <JourneyMetrics stepRows={stepRows} eventTotal={events.data?.total ?? 0} processedTotal={events.data?.processed_total ?? 0} nextStep={nextStep} done={done} />
      <JourneyPicker journeys={rows} currentId={currentId} onSelect={selectJourney} />
      <Pagination offset={journeyOffset} count={rows.length} total={journeys.data?.total ?? 0} onPage={setJourneyOffset} />
      <ProgressCard done={done} total={stepRows.length} />
      <div className="content-grid content-grid--journey">
        <CarePlanPanel steps={steps} stepRows={stepRows} onSubmitStep={submitStep} />
        <UpdatesPanel events={events} eventRows={eventRows} currentId={currentId} onSent={() => { setEventOffset(0); events.refetch(); }} offset={eventOffset} total={events.data?.total} onPage={setEventOffset} />
      </div>
    </>}

    {tab === "plan" && <>
      <JourneyPicker journeys={rows} currentId={currentId} onSelect={selectJourney} />
      <Pagination offset={journeyOffset} count={rows.length} total={journeys.data?.total ?? 0} onPage={setJourneyOffset} />
      <ProgressCard done={done} total={stepRows.length} />
      <CarePlanPanel steps={steps} stepRows={stepRows} onSubmitStep={submitStep} />
    </>}

    {tab === "updates" && <>
      <JourneyPicker journeys={rows} currentId={currentId} onSelect={selectJourney} />
      <Pagination offset={journeyOffset} count={rows.length} total={journeys.data?.total ?? 0} onPage={setJourneyOffset} />
      <div className="content-grid content-grid--journey">
        <UpdatesPanel events={events} eventRows={eventRows} currentId={currentId} onSent={() => { setEventOffset(0); events.refetch(); }} offset={eventOffset} total={events.data?.total} onPage={setEventOffset} />
        <UpdateTypesPanel />
      </div>
    </>}
  </div>;
}

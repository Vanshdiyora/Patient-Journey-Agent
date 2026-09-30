import React, { useState } from "react";
import { CalendarClock, CheckCircle2, Clock3, FileText, HeartPulse, Send } from "lucide-react";
import { meApi } from "../services/api";
import { useAsync } from "../hooks/useAsync";
import { formatDate, getErrorMessage, humanize, toList } from "../utils/constants";
import { Panel, EmptyState, Badge, SkeletonRows, AlertBanner } from "../components";
import { useAuth } from "../context/AuthContext";

const EVENT_TYPES = [
  { value: "SYMPTOM_REPORTED", label: "Report a symptom" },
  { value: "APPOINTMENT_PREFERENCE", label: "Appointment preference" },
  { value: "DOCUMENT_UPLOADED", label: "Document uploaded" },
  { value: "GENERAL_UPDATE", label: "General update" },
  { value: "QUESTION_ASKED", label: "Question for my care team" },
];

function ReportForm({ journeyId, onDone }) {
  const [eventType, setEventType] = useState("SYMPTOM_REPORTED");
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setFeedback(null);
    try {
      // Patient-safe payload only: the backend strips anything else and
      // forces source/verified server-side. No status or step fields.
      await meApi.submitEvent(journeyId, { event_type: eventType, payload: { comment } });
      setFeedback({ tone: "success", text: "Thank you — your update was sent to your care team for review." });
      setComment("");
      onDone?.();
    } catch (err) {
      setFeedback({ tone: "error", text: getErrorMessage(err) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="event-form" onSubmit={submit}>
      <div className="event-form-title"><Send size={14} /> Send an update</div>
      <select value={eventType} onChange={e => setEventType(e.target.value)} style={{ padding: "8px 9px", borderRadius: 7, border: "1px solid #e0e6e4", fontSize: 11 }}>
        {EVENT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
      </select>
      <textarea value={comment} onChange={e => setComment(e.target.value)} rows="3" placeholder="Tell your care team how you're doing…" />
      {feedback && <AlertBanner tone={feedback.tone}>{feedback.text}</AlertBanner>}
      <button className="primary-btn" disabled={busy || !comment.trim()}>{busy ? "Sending…" : "Send update"}</button>
      <p style={{ fontSize: 9, color: "#899592", margin: 0 }}>
        Updates are reviewed by your care team and do not change your treatment plan directly.
      </p>
    </form>
  );
}

export default function MyJourney() {
  const { user } = useAuth();
  const journeys = useAsync(() => meApi.journeys(), []);
  const rows = toList(journeys.data, "items");
  const [selectedId, setSelectedId] = useState(null);
  const currentId = selectedId || rows[0]?.id || null;
  const steps = useAsync(() => (currentId ? meApi.journeySteps(currentId) : Promise.resolve([])), [currentId]);
  const events = useAsync(() => (currentId ? meApi.journeyEvents(currentId) : Promise.resolve([])), [currentId]);
  const stepRows = toList(steps.data);
  const eventRows = toList(events.data);
  const done = stepRows.filter(s => ["COMPLETED", "RESOLVED"].includes(String(s.status).toLowerCase())).length;

  if (journeys.loading) return <div className="skeleton-detail"><i /><i /><i /></div>;
  if (journeys.error) return <div className="empty-state"><strong>Could not load your journey</strong><span>{getErrorMessage(journeys.error)}</span></div>;

  if (!rows.length) {
    return <EmptyState icon={HeartPulse} title="No active journey" text="Your care team has not started a journey for you yet." />;
  }

  const nextStep = stepRows.find(s => !["COMPLETED", "RESOLVED", "CANCELLED"].includes(String(s.status).toLowerCase()));

  return <div>
    <div className="page-heading">
      <div>
        <span className="eyebrow">My health</span>
        <h1>Hello, {humanize(user?.name || user?.email?.split("@")[0])}</h1>
        <p>Follow your care plan and send updates to your care team.</p>
      </div>
    </div>

    <section className="metric-grid">
      <div className="metric-card">
        <div className="metric-icon metric-icon--teal"><HeartPulse size={20} /></div>
        <div className="metric-copy"><span>Care plan progress</span><strong>{stepRows.length ? Math.round(done / stepRows.length * 100) : 0}%</strong><small>{done} of {stepRows.length} steps done</small></div>
      </div>
      <div className="metric-card">
        <div className="metric-icon metric-icon--blue"><Clock3 size={20} /></div>
        <div className="metric-copy"><span>Next step</span><strong>{nextStep ? `Step ${stepRows.indexOf(nextStep) + 1}` : "All done"}</strong><small>{nextStep?.due_at ? `Due ${formatDate(nextStep.due_at)}` : "No pending steps"}</small></div>
      </div>
      <div className="metric-card">
        <div className="metric-icon metric-icon--amber"><FileText size={20} /></div>
        <div className="metric-copy"><span>Updates sent</span><strong>{eventRows.length}</strong><small>{eventRows.filter(e => !e.processed).length} awaiting review</small></div>
      </div>
      <div className="metric-card">
        <div className="metric-icon metric-icon--green"><CheckCircle2 size={20} /></div>
        <div className="metric-copy"><span>Reviewed by team</span><strong>{eventRows.filter(e => e.processed).length}</strong><small>Updates processed</small></div>
      </div>
    </section>

    {rows.length > 1 && (
      <div className="button-group" style={{ marginBottom: 16 }}>
        {rows.map(j => (
          <button key={j.id} className={j.id === currentId ? "primary-btn" : "secondary-btn"} onClick={() => setSelectedId(j.id)}>
            {humanize(j.pathway_name || "Care journey")}
          </button>
        ))}
      </div>
    )}

    <div className="journey-progress">
      <div className="journey-progress-head"><span>Your progress</span><strong>{done} / {stepRows.length} steps completed</strong></div>
      <div className="progress-track"><div className="progress-value" style={{ width: `${stepRows.length ? Math.round(done / stepRows.length * 100) : 0}%` }} /></div>
    </div>

    <div className="content-grid content-grid--journey">
      <Panel wide title="My care plan" subtitle="What you're working on">
        {steps.loading ? <SkeletonRows /> : stepRows.length ? (
          <div className="timeline">{stepRows.map((s, i) => (
            <div className={`timeline-item ${String(s.status).toLowerCase()}`} key={s.id}>
              <div className="timeline-marker">
                {["COMPLETED", "RESOLVED"].includes(String(s.status).toLowerCase()) ? <CheckCircle2 size={17} /> : <CalendarClock size={15} />}
              </div>
              <div className="timeline-content">
                <div className="timeline-top"><strong>Step {i + 1}</strong><Badge kind="status" value={s.status} /></div>
                <div className="timeline-dates">
                  {s.started_at && <span>Started {formatDate(s.started_at, true)}</span>}
                  {s.due_at && <span>Due {formatDate(s.due_at, true)}</span>}
                </div>
              </div>
            </div>
          ))}</div>
        ) : <EmptyState small title="No steps yet" text="Your care plan is being prepared." />}
      </Panel>

      <Panel title="My updates" subtitle="Messages you've sent">
        {events.loading ? <SkeletonRows /> : eventRows.length ? (
          <div className="event-list">{eventRows.slice(0, 8).map(e => (
            <div className="event-row" key={e.id}>
              <div><strong>{humanize(e.event_type)}</strong><span>{formatDate(e.event_time, true)}</span></div>
              <span className={`event-dot ${e.processed ? "event-dot--done" : ""}`} title={e.processed ? "Reviewed" : "Awaiting review"} />
            </div>
          ))}</div>
        ) : <EmptyState small title="No updates yet" text="Use the form to tell your care team how you're doing." />}
        {currentId && <ReportForm journeyId={currentId} onDone={() => events.refetch()} />}
      </Panel>
    </div>
  </div>;
}

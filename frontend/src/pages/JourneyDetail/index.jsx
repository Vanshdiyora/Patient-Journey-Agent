import React, { useState } from "react";
import { ArrowLeft, Play, RefreshCw } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { journeysApi, agentsApi } from "../../services";
import { useAsync } from "../../hooks/useAsync";
import { formatDate, getErrorMessage, toList } from "../../utils";
import { useAuth } from "../../context/AuthContext";
import { canViewObservability } from "../../utils/roles";
import { PageHeading, Panel, ErrorState, Badge, AlertBanner, DetailSkeleton } from "../../components";
import StepsTimeline from "./StepsTimeline";
import JourneyProgress from "./JourneyProgress";
import { ContextPanel, EventsPanel, AgentActivityPanel, ActionsPanel } from "./panels";

export default function JourneyDetail() {
  const { journeyId } = useParams();
  const journey = useAsync(() => journeysApi.get(journeyId), [journeyId]);
  const steps = useAsync(() => journeysApi.steps(journeyId), [journeyId]);
  const events = useAsync(() => journeysApi.events(journeyId, { limit: 100 }), [journeyId]);
  const actions = useAsync(() => journeysApi.actions(journeyId), [journeyId]);
  const agents = useAsync(() => agentsApi.runs({ journey_id: journeyId, limit: 20 }), [journeyId]);

  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const { user } = useAuth();
  const observability = canViewObservability(user);

  if (journey.loading) return <DetailSkeleton />;
  if (journey.error) return <ErrorState error={journey.error} title="Could not load journey" />;

  const j = journey.data;
  const stepRows = toList(steps.data);
  const eventRows = toList(events.data);
  const actionRows = toList(actions.data, "items", "actions");
  const agentRows = toList(agents.data);

  const run = async (type, fn) => {
    setBusy(type);
    setMessage("");
    try {
      await fn();
      setMessage(type === "orchestrate" ? "Orchestration completed." : "Evaluation completed.");
      await journey.refetch();
      await steps.refetch();
    } catch (e) {
      setMessage(getErrorMessage(e));
    } finally {
      setBusy("");
    }
  };

  const addEvent = async (payload) => {
    setBusy("event");
    setMessage("");
    try {
      await journeysApi.addEvent(journeyId, payload);
      setMessage("Event added successfully.");
      await events.refetch();
    } catch (err) {
      setMessage(getErrorMessage(err));
    } finally {
      setBusy("");
    }
  };

  return <div>
    <Link className="back-link" to="/journeys"><ArrowLeft size={16} /> Back to journeys</Link>
    <PageHeading
      eyebrow="Journey execution"
      title={`#${String(j.id).slice(0, 12)}`}
      actions={<>
        <button className="secondary-btn" disabled={!!busy} onClick={() => run("evaluate", () => journeysApi.evaluate(j.id))}>
          <RefreshCw size={16} />{busy === "evaluate" ? "Evaluating…" : "Evaluate"}
        </button>
        <button className="primary-btn" disabled={!!busy} onClick={() => run("orchestrate", () => journeysApi.orchestrate(j.id))}>
          <Play size={16} />{busy === "orchestrate" ? "Orchestrating…" : "Orchestrate"}
        </button>
      </>}
    />
    <div className="heading-meta" style={{ marginTop: -14, marginBottom: 16 }}>
      <Badge kind="status" value={j.status} />
      <Badge kind="priority" value={j.priority} />
      <span>Started {formatDate(j.started_at, true)}</span>
    </div>
    {message && <AlertBanner tone={message.includes("completed") ? "success" : "error"}>{message}</AlertBanner>}

    <JourneyProgress steps={stepRows} />

    <div className="content-grid content-grid--journey">
      <Panel wide title="Journey steps" subtitle="Current pathway state">
        <StepsTimeline steps={stepRows} />
      </Panel>

      {observability && <ContextPanel journeyId={j.id} />}

      <div style={{ display: "contents" }}>
        <EventsPanel journeyId={j.id} eventRows={eventRows} loading={events.loading} busy={busy} onAdd={addEvent} />
        {observability && <AgentActivityPanel agentRows={agentRows} />}
        <ActionsPanel actionRows={actionRows} />
      </div>
    </div>
  </div>;
}

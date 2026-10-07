import React, { useState } from "react";
import { ArrowLeft, Play, RefreshCw } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { journeysApi, agentsApi } from "../../services";
import { useAsync } from "../../hooks/useAsync";
import { formatDate, getErrorMessage, humanize, toList } from "../../utils";
import { useAuth } from "../../context/AuthContext";
import { canViewObservability } from "../../utils/roles";
import { PageHeading, Panel, ErrorState, Badge, AlertBanner, DetailSkeleton } from "../../components";
import { useConfirm } from "../../components/ConfirmModal";
import { useToast } from "../../context/ToastContext";
import StepsTimeline from "./StepsTimeline";
import JourneyProgress from "./JourneyProgress";
import { ContextPanel, EventsPanel, AgentActivityPanel, ActionsPanel } from "./panels";
import AgentRunDetails from "../../components/AgentRunDetails";
import { PATHS } from "../../routes/paths";

export default function JourneyDetail() {
  const { journeyId } = useParams();
  const journey = useAsync(() => journeysApi.get(journeyId), [journeyId]);
  const steps = useAsync(() => journeysApi.steps(journeyId), [journeyId]);
  const events = useAsync(() => journeysApi.events(journeyId, { limit: 100 }), [journeyId]);
  const actions = useAsync(() => journeysApi.actions(journeyId), [journeyId]);
  const agents = useAsync(() => agentsApi.runs({ journey_id: journeyId, limit: 20 }), [journeyId]);

  const [busy, setBusy] = useState("");
  const [busyStepId, setBusyStepId] = useState("");
  const [contextVersion, setContextVersion] = useState(0);
  const [message, setMessage] = useState("");
  const [messageTone, setMessageTone] = useState("success");
  const [runResult, setRunResult] = useState(null);
  const [confirm, confirmModal] = useConfirm();
  const toast = useToast();
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
    const ok = await confirm({
      title: type === "orchestrate" ? "Run orchestration?" : "Re-evaluate this journey?",
      message: type === "orchestrate"
        ? "The orchestration agents will run for this journey and may schedule new actions."
        : "Step statuses will be recomputed from the latest events.",
      confirmLabel: type === "orchestrate" ? "Orchestrate" : "Evaluate",
      intent: "primary",
    });
    if (!ok) return;
    setBusy(type);
    setMessage("");
    if (type === "orchestrate") setRunResult(null);
    try {
      const result = await fn();
      if (type === "orchestrate") setRunResult(result);
      const successText = type === "orchestrate" ? `Orchestration finished: ${humanize(result.status)}.` : "Evaluation completed.";
      setMessage(successText);
      setMessageTone("success");
      toast.success(successText);
      await Promise.allSettled([journey.refetch(), steps.refetch(), events.refetch(), actions.refetch(), agents.refetch()]);
    } catch (e) {
      const errorText = getErrorMessage(e);
      setMessage(errorText);
      setMessageTone("error");
      toast.error(errorText);
      if (type === "orchestrate") await Promise.allSettled([agents.refetch(), actions.refetch()]);
    } finally {
      setBusy("");
    }
  };

  const completeStep = async (step) => {
    const ok = await confirm({
      title: "Confirm step completion?",
      message: `Only confirm this if "${step.name}" has actually been completed. This records your staff account and updates the patient’s care plan.`,
      confirmLabel: "Mark completed",
      intent: "primary",
    });
    if (!ok) return;
    setBusyStepId(step.id);
    try {
      await journeysApi.completeStep(journeyId, step.id);
      await Promise.all([journey.refetch(), steps.refetch(), events.refetch()]);
      setContextVersion(version => version + 1);
      toast.success("Step marked completed. The next eligible step has been evaluated.");
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setBusyStepId("");
    }
  };

  const addEvent = async (payload) => {
    setBusy("event");
    setMessage("");
    try {
      await journeysApi.addEvent(journeyId, payload);
      setMessage("Event added successfully.");
      setMessageTone("success");
      toast.success("Event added successfully.");
      await events.refetch();
    } catch (err) {
      const errorText = getErrorMessage(err);
      setMessage(errorText);
      setMessageTone("error");
      toast.error(errorText);
    } finally {
      setBusy("");
    }
  };

  const updateStepTimeLimit = async (stepId, hours) => {
    setBusyStepId(stepId);
    try {
      await journeysApi.updateStepTimeLimit(journeyId, stepId, hours);
      await Promise.all([journey.refetch(), steps.refetch()]);
      setContextVersion(version => version + 1);
      toast.success("Step time limit updated.");
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setBusyStepId("");
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
    {message && <AlertBanner tone={messageTone}>{message}</AlertBanner>}

    {runResult && <Panel wide className="run-result-panel" title="Latest orchestration result" subtitle="Decision, agent outputs, execution response, and run steps" action={runResult.run_id && <Link className="text-link" to={`${PATHS.agentRuns}?run=${runResult.run_id}`}>Open saved run</Link>}>
      <AgentRunDetails run={runResult} />
    </Panel>}

    <JourneyProgress steps={stepRows} />

    <div className="content-grid content-grid--journey">
      <Panel wide title="Journey steps" subtitle="Current pathway state">
        <StepsTimeline
          steps={stepRows}
          onUpdateTimeLimit={updateStepTimeLimit}
          onComplete={completeStep}
          busyStepId={busyStepId}
          userRole={user?.role}
        />
      </Panel>

      {observability && <ContextPanel key={contextVersion} journeyId={j.id} />}

      <div style={{ display: "contents" }}>
        <EventsPanel journeyId={j.id} eventRows={eventRows} loading={events.loading} busy={busy} onAdd={addEvent} />
        {observability && <AgentActivityPanel agentRows={agentRows} loading={agents.loading} error={agents.error} />}
        <ActionsPanel actionRows={actionRows} loading={actions.loading} error={actions.error} />
      </div>
    </div>
    {confirmModal}
  </div>;
}

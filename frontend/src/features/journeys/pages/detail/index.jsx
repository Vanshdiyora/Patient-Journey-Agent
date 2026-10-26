import React, { useEffect, useState } from "react";
import { ArrowLeft, Play, RefreshCw } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { journeysApi, agentsApi } from "../../../../services/index";
import { useAsync } from "../../../../hooks/useAsync";
import { formatDate, getErrorMessage, humanize, toList } from "../../../../utils/index";
import { useAuth } from "../../../../context/AuthContext";
import { canViewObservability } from "../../../../utils/roles";
import { PageHeading, Panel, ErrorState, Badge, AlertBanner, DetailSkeleton, SkeletonRows } from "../../../../components/index";
import { useConfirm } from "../../../../components/ConfirmModal";
import { useToast } from "../../../../context/ToastContext";
import StepsTimeline from "./StepsTimeline";
import JourneyProgress from "./JourneyProgress";
import { EventsPanel, AgentActivityPanel, ActionsPanel } from "./panels";
import AgentRunDetails, { finalStateLabel } from "../../../../components/AgentRunDetails";
import { PATHS } from "../../../../routes/paths";

export default function JourneyDetail() {
  const { journeyId } = useParams();
  const [eventOffset, setEventOffset] = useState(0);
  const [actionOffset, setActionOffset] = useState(0);
  const [agentOffset, setAgentOffset] = useState(0);
  useEffect(() => { setEventOffset(0); setActionOffset(0); setAgentOffset(0); }, [journeyId]);
  const journey = useAsync(() => journeysApi.get(journeyId), [journeyId]);
  const steps = useAsync(() => journeysApi.steps(journeyId), [journeyId]);
  const events = useAsync(() => journeysApi.events(journeyId, { limit: 10, offset: eventOffset }), [journeyId, eventOffset]);
  const actions = useAsync(() => journeysApi.actions(journeyId, { limit: 10, offset: actionOffset }), [journeyId, actionOffset]);
  const agents = useAsync(() => agentsApi.runs({ journey_id: journeyId, limit: 10, offset: agentOffset }), [journeyId, agentOffset]);

  const [busy, setBusy] = useState("");
  const [busyStepId, setBusyStepId] = useState("");
  const [message, setMessage] = useState("");
  const [messageTone, setMessageTone] = useState("success");
  const [runResult, setRunResult] = useState(null);
  const [confirm, confirmModal] = useConfirm();
  const toast = useToast();
  const { user } = useAuth();
  const observability = canViewObservability(user);

  if (journey.error && journey.data?.id !== journeyId) return <ErrorState error={journey.error} title="Could not load journey" />;
  if (journey.data?.id !== journeyId) return <DetailSkeleton />;

  const j = journey.data;
  const stepRows = toList(steps.data);
  const eventRows = toList(events.data, "items");
  const actionRows = toList(actions.data, "items", "actions");
  const agentRows = toList(agents.data, "items");

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
      const successText = type === "orchestrate" ? `Orchestration finished: ${finalStateLabel(result.status)}.` : "Evaluation completed.";
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
      toast.success("Step marked completed. The next eligible step has been evaluated.");
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setBusyStepId("");
    }
  };

  const decideAction = async (action, approve) => {
    const ok = await confirm({
      title: approve ? "Approve this action?" : "Reject this action?",
      message: approve
        ? `"${humanize(action.action_type)}" will be carried out now and recorded under your name.`
        : `"${humanize(action.action_type)}" will be cancelled and nothing will be sent.`,
      confirmLabel: approve ? "Approve" : "Reject",
      intent: approve ? "primary" : "danger",
    });
    if (!ok) return;
    setBusy(`action-${action.id}`);
    try {
      const result = approve ? await journeysApi.approveAction(action.id) : await journeysApi.rejectAction(action.id);
      const failed = result.status === "FAILED";
      (failed ? toast.error : toast.success)(
        failed ? `The action could not be completed: ${result.error_message || "unknown error"}`
          : approve ? "Action approved and carried out." : "Action rejected."
      );
      await Promise.allSettled([actions.refetch(), journey.refetch(), steps.refetch(), agents.refetch()]);
    } catch (error) {
      toast.error(getErrorMessage(error));
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
      setMessageTone("success");
      toast.success("Event added successfully.");
      if (eventOffset === 0) await events.refetch();
      else setEventOffset(0);
      return true;
    } catch (err) {
      const errorText = getErrorMessage(err);
      setMessage(errorText);
      setMessageTone("error");
      toast.error(errorText);
      return false;
    } finally {
      setBusy("");
    }
  };

  const addStepEvidence = async (step, details, file, evidenceType, approvalConfirmed) => {
    setBusyStepId(step.id);
    try {
      await journeysApi.addStepEvidence(journeyId, step.id, details, file, evidenceType, approvalConfirmed);
      await Promise.all([steps.refetch(), events.refetch(), journey.refetch()]);
      toast.success(evidenceType === "APPROVAL"
        ? "Approval evidence recorded. The journey was re-evaluated."
        : "Step evidence saved. The journey was re-evaluated.");
      return true;
    } catch (error) {
      toast.error(getErrorMessage(error));
      return false;
    } finally {
      setBusyStepId("");
    }
  };

  const updateStepTimeLimit = async (stepId, hours) => {
    setBusyStepId(stepId);
    try {
      await journeysApi.updateStepTimeLimit(journeyId, stepId, hours);
      await Promise.all([journey.refetch(), steps.refetch()]);
      toast.success("Step time limit updated.");
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setBusyStepId("");
    }
  };

  return <div>
    <Link className="back-link" to={`/patients/${j.patient_id}`}><ArrowLeft size={16} /> Back to patient</Link>
    <PageHeading
      eyebrow="Care journey"
      title={j.pathway_name || "Care journey"}
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
      <span className="journey-reference">Journey #{String(j.id).slice(0, 8)}</span>
      <span>Started {formatDate(j.started_at, true)}</span>
    </div>
    {message && <AlertBanner tone={messageTone}>{message}</AlertBanner>}
    {busy === "orchestrate" && !runResult && <Panel wide className="run-result-panel" title="Orchestration running" subtitle="The backend is evaluating the journey and recording agent activity.">
      <div className="run-pending" role="status" aria-live="polite">
        <RefreshCw size={18} className="run-pending-icon" />
        <span><strong>Status: Running</strong>The result will appear here when the backend finishes.</span>
      </div>
    </Panel>}

    {runResult && <Panel wide className="run-result-panel" title="Latest orchestration result" subtitle="Decision, agent outputs, execution response, and run steps" action={runResult.run_id && <Link className="text-link" to={`${PATHS.agentRuns}?run=${runResult.run_id}`}>Open saved run</Link>}>
      <AgentRunDetails run={runResult} />
    </Panel>}

    {steps.loading ? <div className="journey-progress" role="status">Loading journey steps…</div>
      : !steps.error && <JourneyProgress steps={stepRows} />}

    <div className="content-grid content-grid--journey">
      <Panel wide title="Journey steps" subtitle="Current pathway state">
        {steps.loading ? <SkeletonRows count={4} /> : steps.error ?
          <ErrorState error={steps.error} title="Could not load journey steps" /> :
          <StepsTimeline
            steps={stepRows}
            onUpdateTimeLimit={updateStepTimeLimit}
            onComplete={completeStep}
            onAddEvidence={addStepEvidence}
            busyStepId={busyStepId}
            userRole={user?.role}
          />}
      </Panel>

      <div style={{ display: "contents" }}>
        <EventsPanel journeyId={j.id} eventRows={eventRows} loading={events.loading} error={events.error} busy={busy} onAdd={addEvent} onDownloadEvidence={journeysApi.downloadStepEvidence} offset={eventOffset} total={events.data?.total} onPage={setEventOffset} />
        {observability && <AgentActivityPanel agentRows={agentRows} loading={agents.loading} error={agents.error} offset={agentOffset} total={agents.data?.total} onPage={setAgentOffset} />}
        <ActionsPanel actionRows={actionRows} loading={actions.loading} error={actions.error} busy={busy} onDecide={decideAction} offset={actionOffset} total={actions.data?.total} onPage={setActionOffset} />
      </div>
    </div>
    {confirmModal}
  </div>;
}

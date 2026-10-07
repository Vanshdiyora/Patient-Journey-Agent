import React from "react";
import { humanize } from "../utils";

const componentName = value => humanize(String(value || "").replace(/([a-z])([A-Z])/g, "$1 $2"));

function JsonDetails({ title, value, defaultOpen = false }) {
  if (value == null) return null;
  return <details className="run-json" open={defaultOpen || undefined}><summary>{title}</summary><pre>{JSON.stringify(value, null, 2)}</pre></details>;
}

function Outcome({ item }) {
  const output = item.output || {};
  const action = item.component === "action_executor" ? output : output.action_execution;
  return <div className="run-outcome">
    <strong>{componentName(item.component)}</strong>
    {action ? <>
      <span>{humanize(action.action_type)} · {humanize(action.status)}{action.duplicate ? " · Already recorded" : ""}</span>
      <JsonDetails title="Execution response" value={action.response} defaultOpen />
    </> : <>
      {output.action_type && <span>Suggested action: {humanize(output.action_type)}</span>}
      {output.assessment && <span>Assessment: {output.assessment}</span>}
      {output.reason && <p>{output.reason}</p>}
      <JsonDetails title="Full output" value={output} defaultOpen />
    </>}
  </div>;
}

/** Works with the live POST response and the saved orchestration audit record. */
export default function AgentRunDetails({ run }) {
  const saved = run.run_type === "ORCHESTRATION";
  const output = saved ? run.output || {} : run;
  const decision = output.decision;
  const outcomes = output.outcomes || [];
  const calls = saved ? run.tool_calls || [] : run.calls || [];
  if (!saved && !run.calls) {
    const agentOutput = run.output || {};
    return <div className="run-detail-body">
      {agentOutput.reason && <p className="run-reason">{agentOutput.reason}</p>}
      {agentOutput.next_capability && <p><b>Direction:</b> {humanize(agentOutput.next_capability)}</p>}
      {agentOutput.action_type && <p><b>Suggested action:</b> {humanize(agentOutput.action_type)}</p>}
      {agentOutput.assessment && <p><b>Assessment:</b> {agentOutput.assessment}</p>}
      <JsonDetails title="Full agent output" value={agentOutput} defaultOpen />
      <JsonDetails title="Input context" value={run.input_context} />
      {run.tool_calls?.length > 0 && <JsonDetails title="Tool calls" value={run.tool_calls} />}
      {run.error_message && <p className="form-error">{run.error_message}</p>}
    </div>;
  }
  return <div className="run-detail-body">
    <div className="run-summary">
      <span><b>Final state</b>{humanize(run.status)}</span>
      <span><b>Supervisor direction</b>{humanize(decision?.next_capability)}</span>
      {decision?.target_step_id && <span><b>Target step</b><code>{decision.target_step_id}</code></span>}
    </div>
    {decision?.reason && <p className="run-reason">{decision.reason}</p>}
    {outcomes.length > 0 ? <div className="run-outcomes"><h4>Agent and action outputs</h4>{outcomes.map((item, index) => <Outcome key={index} item={item} />)}</div> : <p className="run-reason">No agent action was produced in this run.</p>}
    <div className="run-trace"><h4>Run steps</h4><ol>{calls.map((call, index) => <li key={index}>
      <strong>{componentName(call.component)}</strong>
      <span>{call.operation ? humanize(call.operation) : call.decision?.next_capability ? `Chose ${humanize(call.decision.next_capability)}` : call.component === "action_executor" && call.output?.action_type ? `Executed ${humanize(call.output.action_type)}` : call.output?.action_type ? `Suggested ${humanize(call.output.action_type)}` : call.outcome ? humanize(call.outcome) : "Returned output"}</span>
      {call.reason && <small>{call.reason}</small>}
    </li>)}</ol></div>
    <JsonDetails title="Final result (JSON)" value={output.result} />
    <JsonDetails title="Complete run trace (JSON)" value={calls} />
    {saved && <JsonDetails title="Input context" value={run.input_context} />}
    {run.error_message && <p className="form-error">{run.error_message}</p>}
    <p className="run-boundary">Operational support only. Action integrations currently use mock services; staff should verify follow-up.</p>
  </div>;
}

/** Choose a card only when the tool returned data worth scanning visually. */
export function needsDataCard(toolResult) {
  if (toolResult?.status !== "ok" || !toolResult.result?.data) return false;
  const data = toolResult.result.data;
  switch (toolResult.tool) {
    case "search_patients":
      return Array.isArray(data.patients) && data.patients.length > 0;
    case "get_patient_summary":
      return Boolean(data.patient) && Array.isArray(data.journeys) && data.journeys.length > 0;
    case "list_pathways":
      return Array.isArray(data.pathways) && data.pathways.length > 0;
    case "list_journeys":
      return Array.isArray(data.journeys) && data.journeys.length > 0;
    case "get_journey_steps":
      return Boolean(data.journey) && Array.isArray(data.steps) && data.steps.length > 0;
    case "get_pending_tasks":
      return Array.isArray(data.journeys) && data.journeys.some(journey => journey.tasks?.length > 0);
    case "list_patients":
      return Array.isArray(data.patients) && data.patients.length > 0;
    case "get_journey_events":
      return Array.isArray(data.events) && data.events.length > 0;
    case "get_dashboard_summary":
      return Boolean(data.metrics);
    case "list_exceptions":
      return Array.isArray(data.exceptions) && data.exceptions.length > 0;
    case "list_users":
      return Array.isArray(data.users) && data.users.length > 0;
    case "get_chat_audit":
      return Array.isArray(data.entries) && data.entries.length > 0;
    default:
      return false;
  }
}

export function readResultPresentation(message) {
  const results = Array.isArray(message?.meta?.tool_results) ? message.meta.tool_results : [];
  const lastResult = [...results].reverse().find(result => result.status === "ok" && result.result?.data);
  if (needsDataCard(lastResult)) return { kind: "card", result: lastResult };

  const text = message?.content?.trim()
    || lastResult?.result?.summary
    || [...results].reverse().find(result => result.error)?.error
    || "I couldn't find a result for that request.";
  return { kind: "text", text };
}

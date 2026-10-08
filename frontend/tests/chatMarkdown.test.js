import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { createServer } from "vite";

test("assistant replies render common formats without raw markup or executable HTML", async () => {
  const vite = await createServer({
    server: { middlewareMode: true },
    optimizeDeps: { noDiscovery: true, include: [] },
    appType: "custom",
  });
  try {
    const { default: ChatMessageItem } = await vite.ssrLoadModule("/src/components/chat/ChatMessageItem.jsx");
    const render = (message, user) => renderToStaticMarkup(
      React.createElement(MemoryRouter, null, React.createElement(ChatMessageItem, { message, user }))
    );
    const content = [
      "**Patient:** Vansh Diyora",
      "",
      "1. Review",
      "2. Surgery",
      "",
      "| Step | Status |",
      "| --- | --- |",
      "| Review | Ready |",
      "",
      "`ABC-123` [Details](https://example.com)",
      "[Unsafe](javascript:alert(1))",
      "<script>alert('unsafe')</script>",
    ].join("\n");
    const html = render({ role: "assistant", content, meta: {} });

    assert.match(html, /<strong>Patient:<\/strong>/);
    assert.match(html, /<ol>/);
    assert.match(html, /chat-table-scroll/);
    assert.match(html, /<th>Step<\/th>/);
    assert.match(html, /<code>ABC-123<\/code>/);
    assert.match(html, /href="https:\/\/example.com"/);
    assert.doesNotMatch(html, /href="javascript:/);
    assert.doesNotMatch(html, /<script>|alert\(&#x27;unsafe&#x27;\)/);
    assert.doesNotMatch(html, /\| --- \|/);

    const actionHtml = render({ role: "assistant", content: "", meta: {
      action_result: { status: "executed", tool: "complete_step", result: { summary: "**Done** today" } },
    } });
    assert.match(actionHtml, /<strong>Done<\/strong> today/);

    const journeyMessage = { role: "assistant", content: "Found journeys", meta: { tool_results: [{
      tool: "list_journeys", status: "ok", result: { data: { journeys: [
        { id: "journey-1", pathway_name: "Knee recovery", patient_name: "Vansh", status: "blocked" },
      ] } },
    }] } };
    const staffHtml = render(journeyMessage, { role: "CLINICIAN" });
    assert.match(staffHtml, /href="\/journeys\/journey-1"/);
    assert.match(staffHtml, /aria-label="Open Knee recovery for Vansh"/);

    const patientHtml = render(journeyMessage, { role: "PATIENT" });
    assert.match(patientHtml, /href="\/my-journey\?journeyId=journey-1"/);

    const pathwaysHtml = render({ role: "assistant", content: "", meta: { tool_results: [{
      tool: "list_pathways", status: "ok", result: { data: { pathways: [
        { id: "pathway-1", name: "Recovery", steps: ["Review", "Surgery"] },
      ] } },
    }] } }, { role: "CLINICIAN" });
    assert.match(pathwaysHtml, /<details/);
    assert.match(pathwaysHtml, /<li>Review<\/li>/);

    const toolHtml = (tool, data, user = { role: "CLINICIAN" }) => render({
      role: "assistant", content: "", meta: { tool_results: [{ tool, status: "ok", result: { data } }] },
    }, user);
    const linkedResults = [
      ["search_patients", { patients: [{ id: "patient-1", name: "Vansh" }] }, "/patients/patient-1"],
      ["get_patient_summary", { patient: { id: "patient-1", name: "Vansh" }, journeys: [{ id: "journey-1" }] }, "/patients/patient-1"],
      ["list_patients", { patients: [{ id: "patient-1", name: "Vansh" }] }, "/patients/patient-1"],
      ["get_journey_steps", { journey: { id: "journey-1" }, steps: [{ id: "step-1", name: "Review" }] }, "/journeys/journey-1"],
      ["get_pending_tasks", { journeys: [{ journey_id: "journey-1", tasks: [{ id: "step-1", name: "Review" }] }] }, "/journeys/journey-1"],
      ["get_journey_events", { journey_id: "journey-1", events: [{ id: "event-1", event_type: "review" }] }, "/journeys/journey-1"],
      ["get_dashboard_summary", { metrics: { active_journeys: 1 } }, "/journeys"],
      ["list_exceptions", { exceptions: [{ id: "exception-1", journey_id: "journey-1", title: "Blocked" }] }, "/journeys/journey-1"],
    ];
    for (const [tool, data, href] of linkedResults) {
      assert.ok(toolHtml(tool, data).includes(`href="${href}"`), `${tool} should link to ${href}`);
    }
    assert.match(toolHtml("list_users", { users: [{ id: "user-1", display_name: "Alex" }] }, { role: "ADMIN" }), /href="\/users"/);
    assert.doesNotMatch(toolHtml("list_journeys", { journeys: [{ pathway_name: "Missing ID" }] }), /chat-result-link/);
  } finally {
    await vite.close();
  }
});

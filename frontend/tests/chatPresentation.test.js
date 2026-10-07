import test from "node:test";
import assert from "node:assert/strict";
import { readResultPresentation } from "../src/components/chat/presentation.js";

const result = (tool, data, summary = "Tool summary") => ({
  tool, status: "ok", result: { data, summary },
});

test("detailed journey data uses one card", () => {
  const message = {
    content: "Repeated journey text",
    meta: { tool_results: [
      result("search_patients", { patients: [{ id: "p1" }] }),
      result("get_journey_steps", { journey: { id: "j1" }, steps: [{ id: "s1" }] }),
    ] },
  };
  const presentation = readResultPresentation(message);
  assert.equal(presentation.kind, "card");
  assert.equal(presentation.result.tool, "get_journey_steps");
});

test("empty search uses the assistant's normal text", () => {
  const message = {
    content: "I couldn't find a matching patient.",
    meta: { tool_results: [result("search_patients", { patients: [] })] },
  };
  assert.deepEqual(readResultPresentation(message), {
    kind: "text", text: "I couldn't find a matching patient.",
  });
});

test("empty tasks use tool summary when the assistant has no text", () => {
  const message = {
    content: "",
    meta: { tool_results: [result("get_pending_tasks", { journeys: [] }, "No open tasks.")] },
  };
  assert.deepEqual(readResultPresentation(message), { kind: "text", text: "No open tasks." });
});

test("ordinary answers remain normal text", () => {
  assert.deepEqual(readResultPresentation({ content: "Hello", meta: {} }), { kind: "text", text: "Hello" });
});

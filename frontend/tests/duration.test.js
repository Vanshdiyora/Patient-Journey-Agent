import test from "node:test";
import assert from "node:assert/strict";
import { formatDurationHours, milestoneLabel, preferredUnit } from "../src/utils/duration.js";

test("pathway allowances read as weeks, days, and hours", () => {
  assert.equal(formatDurationHours(24), "1 day");
  assert.equal(formatDurationHours(36), "1 day 12 hours");
  assert.equal(formatDurationHours(192), "1 week 1 day");
  assert.equal(formatDurationHours(null), "Not set");
  assert.equal(preferredUnit(168), "weeks");
  assert.equal(preferredUnit(48), "days");
});

test("journey milestones use day and week labels", () => {
  assert.equal(milestoneLabel(0), "At the start");
  assert.equal(milestoneLabel(3), "Day 3");
  assert.equal(milestoneLabel(7), "Week 1");
  assert.equal(milestoneLabel(28), "Week 4");
});

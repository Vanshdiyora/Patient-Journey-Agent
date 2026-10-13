import test from "node:test";
import assert from "node:assert/strict";
import { durationHoursFromParts, formatDurationHours, milestoneLabel, preferredUnit, splitDurationHours } from "../src/utils/duration.js";

test("pathway allowances read as weeks, days, and hours", () => {
  assert.equal(formatDurationHours(24), "1 day");
  assert.equal(formatDurationHours(36), "1 day 12 hours");
  assert.equal(formatDurationHours(192), "1 week 1 day");
  assert.equal(formatDurationHours(204), "1 week 1 day 12 hours");
  assert.equal(formatDurationHours(null), "Not set");
  assert.equal(preferredUnit(168), "weeks");
  assert.equal(preferredUnit(48), "days");
});

test("duration parts carry hours into days and days into weeks", () => {
  assert.deepEqual(splitDurationHours(23), { weeks: 0, days: 0, hours: 23 });
  assert.deepEqual(splitDurationHours(24), { weeks: 0, days: 1, hours: 0 });
  assert.deepEqual(splitDurationHours(191), { weeks: 1, days: 0, hours: 23 });
  assert.equal(durationHoursFromParts({ weeks: 1, days: 1, hours: 12 }), 204);
});

test("journey milestones use day and week labels", () => {
  assert.equal(milestoneLabel(0), "At the start");
  assert.equal(milestoneLabel(3), "Day 3");
  assert.equal(milestoneLabel(7), "Week 1");
  assert.equal(milestoneLabel(28), "Week 4");
});

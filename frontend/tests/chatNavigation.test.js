import test from "node:test";
import assert from "node:assert/strict";
import { journeyLink, metricLink, patientLink, usersLink } from "../src/components/chat/navigation.js";

const staff = { role: "CLINICIAN" };
const patient = { role: "PATIENT" };

test("chat result links respect role and record ids", () => {
  assert.equal(journeyLink("journey-1", staff), "/journeys/journey-1");
  assert.equal(journeyLink("journey-1", patient), "/my-journey?journeyId=journey-1");
  assert.equal(patientLink("patient-1", staff), "/patients/patient-1");
  assert.equal(patientLink("patient-1", patient), "/my-journey");
  assert.equal(journeyLink(null, staff), null);
  assert.equal(patientLink(null, staff), null);
  assert.equal(journeyLink("journey-1", null), null);
});

test("summary and admin links go to accessible pages", () => {
  assert.equal(metricLink("Blocked journeys", staff), "/journeys");
  assert.equal(metricLink("Open exceptions", staff), "/exceptions");
  assert.equal(metricLink("Patients", staff), "/patients");
  assert.equal(metricLink("Patients", patient), null);
  assert.equal(usersLink({ role: "ADMIN" }), "/users");
  assert.equal(usersLink(staff), null);
});

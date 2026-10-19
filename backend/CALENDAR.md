# Patient journey calendar

Apply `migrations/20261019_add_journey_calendar.sql` before running this version
against an existing PostgreSQL database. New databases receive it through
`scripts/setup_database.py`. The migration is additive and can be rerun.

Bookings extend `journey_steps`; an event ID is the journey step UUID. There
is at most one current booking per activity. Unbooked activities appear at
their action deadline, or their planned pathway milestone when no deadline
exists. Activities without any target date can be booked using **Book activity**.
These planned dates are labelled explicitly and never imply a confirmed time.

| Role | Visible patients | Scheduling |
| --- | --- | --- |
| Admin | All | Create, update, reschedule, cancel |
| Clinician | `patients.assigned_clinician_id` matches authenticated user | Same actions for assigned patients |
| Care coordinator | Explicit `staff_patient_assignments` grant | Same actions for assigned patients |
| Patient | Authenticated `users.patient_id` only | Read only |

The Patients list, patient profile, patient journeys, calendar, filter options,
and event details use the same scope. Unauthorized object reads return 404.
Staff cannot grant themselves access using the legacy `/patients/{id}/claim`
route; administrators grant assignments using the existing admin endpoints.
Identity, role, and patient linkage are loaded from the authenticated database
account. The auth response includes the account's own `patient_id` for navigation.

## API

All paths are under `/api/v1/calendar` and require bearer authentication.

| Method / path | Behavior |
| --- | --- |
| `GET /events` | Required timezone-aware `start` and exclusive `end`, at most 93 days apart. Booking overlaps are included. Filters: `search`, `patient_id`, `clinician_id`, `coordinator_id`, `journey_status`, `status`. Sorted by event time then step ID; `limit` 1–1000, `offset` ≥ 0. |
| `GET /options` | Permitted patients and assigned staff. Optional scoped `patient_id` adds bookable journey activities. |
| `GET /events/{step_id}` | Live step, patient, care team, journey progress, booking, and visible conflict count. |
| `POST /events` | Create a booking for `journey_step_id`. |
| `PATCH /events/{step_id}` | Edit staff/time or rebook a cancelled booking. A time change marks it rescheduled. |
| `POST /events/{step_id}/cancel` | Cancel the booking while retaining the pathway activity. |

Create/update bodies contain `starts_at`, `ends_at`, optional
`assigned_staff_id`, the current `revision`, and `confirmed: true`. Cancellation
requires `revision` and `confirmed: true`. Unexpected fields are rejected.
Start/end require explicit timezone offsets, are stored as UTC TIMESTAMPTZ, and
must form an interval no longer than seven days. The browser displays times
in its named local timezone and converts local input to UTC for submission.

The UI requires a confirmation dialog before every write. Staff must belong
to the patient's current care team and be active. Transactional journey,
patient, step, and staff locks serialize changes and availability checks;
stale revisions and patient/staff time conflicts return 409. Conflicts outside
the user's scope return a generic availability error without patient identity.

Calendar booking fields are also returned by the existing journey step APIs
and displayed in staff and patient timelines. Completed/cancelled clinical
steps are reflected immediately without a second status store. Booking changes
never complete a clinical step or alter its action deadline. Each change adds
a processed `SCHEDULE_CREATED`, `SCHEDULE_UPDATED`, or `SCHEDULE_CANCELLED`
patient event containing the actor and before/after schedule in the same transaction.


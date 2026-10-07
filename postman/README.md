# Postman API test walkthrough

Import `Patient-Journey-Orchestrator.postman_collection.json` into Postman. The collection has a `baseUrl` variable set to `http://localhost:8000`, patient demo credentials, and a shared `token` variable. Set the clinician, coordinator, and admin email variables to active accounts from the local user seed. The seeded initial password is `Test@123` when accounts were created by the provided seed/sync process.

For Insomnia, import the native v5 YAML file `Patient-Journey-Orchestrator.insomnia.yaml` using **Import → File**. Select this `.yaml` file, not either `.json` file. The YAML validates against Insomnia's published v5.1 schema. In Insomnia's **Base Environment**, set `clinicianEmail`, `coordinatorEmail`, and `adminEmail` to active accounts for the matching roles. After each Login request, copy `access_token` from its response into the environment's `token` value. Copy IDs from list responses into `patientJourneyId`, `patientId`, `journeyId`, or `exceptionId` as indicated by the request descriptions.

## Before you run it

1. Start PostgreSQL and confirm the local database contains the schema and seed data. For a fresh database, use the SQL commands in `backend/README.md`.
2. Ensure the patient portal migration and `backend/scripts/seed_demo_patient_portal.py` have been run if you want to use the four dedicated patient demo users. Run the script from `backend`.
3. Start FastAPI on port 8000 and check `GET http://localhost:8000/api/v1/health` returns `status: ok` and `database: connected`.
4. Configure `MAQ_AI_ENABLED=true` and a valid `MAQ_AI_API_KEY` in `backend/.env` for agent orchestration and chat. Restart the backend after changing environment values. Without an available LLM, normal REST endpoints work, but orchestration/chat can fail.
5. In Postman, set `clinicianEmail`, `coordinatorEmail`, and `adminEmail` collection variables to accounts whose roles match those names. The active local seed JSON is `db/users_and_patients.json`; use a plain email value.

## Recommended sequence

Run requests manually in this order. The login requests automatically replace the collection's `token`; that token is then sent as a bearer token on later requests.

1. **Health and authentication:** run Health check, then Login — Patient, then Who am I. Confirm role is `PATIENT`.
2. **Patient self-service:** run Get profile, List my journeys, Get my journey, steps, and events. `patientJourneyId` is set from the first journey. Submit patient update, then list events again. Expect the event source to be `patient-portal` and `processed` to be false. The patient staff-list request should return 403.
3. **Clinician staff workflow:** run Login — Clinician (this replaces the patient token). Verify role with Who am I. Run dashboard, list patients (Aisha), get patient, and list that patient's journeys. The first journey ID is captured as `journeyId`. Then inspect journey, steps, and orchestration context.
4. Run Evaluate journey. This exercises deterministic dependency/deadline logic and does not call the LLM.
5. Run Orchestrate journey only when ready to exercise agents. It may choose to wait, assess with Journey Intelligence, select a Coordination action, execute a mock integration action, or escalate. Inspect the response `decision`, `result`, and `calls`; then run journey action executions and agent runs to inspect persisted records. A successful request does not necessarily change step completion.
6. Inspect events and exceptions. Use Resolve exception only when `exceptionId` was captured and you intend to change that demo exception's status. Resolving an exception does not satisfy the underlying clinical dependency.
7. **Care Coordinator (optional role coverage):** Login — Care Coordinator replaces the token. Run dashboard, blocked-patient and exception filters; optionally orchestrate the selected journey.
8. **Admin (optional role coverage):** Login — Admin replaces the token. List/search users and verify user-management access. Role/status PATCH requests mutate accounts; only run them on a safe test identity and restore the original value. Do not deactivate your only admin.
9. **Chat (optional):** with a configured LLM and whichever role token you want, create a chat session and send a message. Inspect the returned assistant text and `meta.pending_action`. Only manually run Confirm if you explicitly approve the proposed mutation; otherwise run Reject. Chat sessions/messages are persisted.

## Variables and IDs

- `patientJourneyId` is captured from the patient's first journey.
- `patientId` and `journeyId` are captured after the staff patient search and journey-list requests.
- `exceptionId` is captured from the first exception returned. If there are no exceptions, skip Resolve exception.
- The collection deliberately shares one bearer `token`. Each role login replaces it; log in again as the role required before running role-restricted endpoints.

The API currently gives staff global record scope because assignment-level scoping is not implemented. Patient endpoints are restricted to the logged-in user's linked patient record.

## Collection coverage

Health/auth, patient profile and own journeys/events, patient RBAC denial, staff dashboard/patient/journey/event/evaluation/orchestration, exceptions, action registry/executions, agent run audit, clinician admin denial, admin user management, chat REST sessions/messages/confirmation, plus a WebSocket chat connection note.

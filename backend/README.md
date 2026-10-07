# Patient Journey Orchestrator — 3-Agent Backend

This backend implements the architecture from the project approach document:

- Event Processor
- Deterministic control plane
- Journey Intelligence Agent
- Coordination Agent
- Supervisor Agent
- LangGraph conditional supervisor loop
- Action Registry
- Verification and idempotency
- Mock scheduling / communication / document / clinical-event services
- Audit / agent trace persistence
- PostgreSQL as the source of truth
- MAQ AI through the OpenAI-compatible API at `https://llm.maqsoftware.net/v1`

All protected API routes require an email/password login and a signed bearer token. User passwords are stored as bcrypt hashes.

## Existing database

This code expects the PostgreSQL schema/seed already created for Patient Journey Orchestrator. It does **not** run `Base.metadata.create_all()` against the existing database.

The SQL seed previously supplied for this project creates the synthetic data.

For an empty local PostgreSQL database, run these from the repository root:

```powershell
psql -h localhost -U postgres -d patient_journey_orchestrator -f "db/Create Tables.sql"
psql -h localhost -U postgres -d patient_journey_orchestrator -f "db/patient_journey_orchestrator_seed.sql"
psql -h localhost -U postgres -d patient_journey_orchestrator -f "backend/migrations/20261007_add_step_time_limits.sql"
psql -h localhost -U postgres -d patient_journey_orchestrator -f "backend/migrations/20261007_02_add_step_owners.sql"
```

The seed creates 1,200 staff accounts and 1,200 patient accounts. Each patient
has a unique email and a linked `PATIENT` user row. All seed passwords start as
`Test@123`; PostgreSQL `pgcrypto` stores bcrypt hashes rather than raw
passwords. It also generates synthetic clinical-like data.

## Patient portal demo accounts

Patient records support an optional email for compatibility with older imported
rows. A portal account is stored in `users` with `role = PATIENT` and its
`patient_id` linked to exactly one patient. Patient-scoped endpoints use that
link to return only the authenticated patient's own journey.

For a legacy existing database that also needs the optional patient email
column and demo portal accounts, run these from the repository root:

```powershell
psql -h localhost -U postgres -d patient_journey_orchestrator -f "backend/migrations/20260930_add_patient_email.sql"
psql -h localhost -U postgres -d patient_journey_orchestrator -f "backend/migrations/20261007_add_step_time_limits.sql"
psql -h localhost -U postgres -d patient_journey_orchestrator -f "backend/migrations/20261007_02_add_step_owners.sql"
python "backend/scripts/seed_demo_patient_portal.py"
```

If your shell has a non-boolean `DEBUG` environment variable, run
`$env:DEBUG = "false"` first so the settings loader can start.

This creates four additional synthetic patients with one journey each and
matching portal accounts. Their initial password is `Test@123`, stored as a
bcrypt hash.

## Starting a patient's journey

A patient account is linked to one `patients.id` through `users.patient_id`.
After login, the patient portal loads `GET /api/v1/me/journeys` and shows the
journeys for that patient only. A new patient account therefore starts with an
empty care plan until staff starts a journey.

Administrators can create active pathway templates and edit an active pathway
from the right-side drawer in **Care pathways**. Saving an edit creates a new
active version and makes the previous version inactive. Existing patient
journeys keep their original pathway and steps; future journeys use the new
version. Retained steps carry their dependencies and action rules forward.
Each ordered step has a code, name, type, details, and time limit in hours.
Administrators also select a responsible role for every step: patient,
clinician, care coordinator, administrator, general staff, or agent. Steps
created in the create form are required. Editors can change whether a step is
required. Only administrators can create or edit pathway templates.

Staff can open **Patients → patient profile → Start a care journey**, select an
active pathway and priority, review or override each step's time limit for
that patient, then submit. The backend creates the journey and a snapshot of
its pathway steps and limits together. A step's timer starts when the step
first becomes `READY`; later steps receive their due date only when they
become ready. Staff can adjust an unfinished step's time limit from the staff
journey detail page. The patient sees the pathway name, step details, time
limits, due dates and progress on **My Journey**. Staff cannot start another
active journey for the same patient and pathway until the existing one is
completed or cancelled.

On the staff journey detail page, a staff member can mark a `READY` or
`IN_PROGRESS` step complete after confirming the work was actually done. The
server records a completion event with the confirming staff user and
reevaluates the journey so an eligible next step can become ready. Patients
cannot self-verify completion. For a patient-owned step, the patient submits a
short completion note from **My Journey**; this remains pending until staff
reviews it and confirms completion. Clinician-, coordinator-, and
administrator-owned steps are restricted to the matching role (administrators
may confirm clinician/coordinator work); general staff steps can be confirmed
by any staff role. Agent-owned steps can be completed only when an allowed
agent action succeeds and passes the action verification layer. The current
action integrations are mocks, so agent-owned completion is demonstration
behavior and must not be treated as a production clinical integration.

### Upgrade an existing database

Run these commands from the repository root, using the same database and
credentials configured in `backend/.env` (`DATABASE_URL`). For the current
`column pathway_steps.owner_role does not exist` error, run the ownership
migration (the second command). If the time-limit migration has not previously
been applied, run both in order:

```powershell
psql -h localhost -U postgres -d patient_journey_orchestrator -f "backend/migrations/20261007_add_step_time_limits.sql"
psql -h localhost -U postgres -d patient_journey_orchestrator -f "backend/migrations/20261007_02_add_step_owners.sql"
```

If only the `owner_role` columns are missing, run just:

```powershell
psql -h localhost -U postgres -d patient_journey_orchestrator -f "backend/migrations/20261007_02_add_step_owners.sql"
```

If your PostgreSQL username, host, port, or database name differs from the
example, replace those connection values. The `20260930_add_patient_email.sql`
migration is separate; run it only if your existing database also lacks the
optional `patients.email` column needed by the patient portal.

After applying the migration, restart the backend. To verify the required
columns exist, run:

```sql
SELECT table_name, column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND (
      (table_name = 'pathway_steps' AND column_name IN ('owner_role', 'time_limit_hours'))
      OR (table_name = 'journey_steps' AND column_name IN ('owner_role', 'time_limit_hours'))
  )
ORDER BY table_name;
```

The query should return both `owner_role` and `time_limit_hours` for each
table. Do not rerun the bulk seed SQL against an existing database; it deletes
and recreates its synthetic records.

The patient must have a `PATIENT` user account linked to that same patient
record. Seeded patients already have linked accounts; staff should confirm the
link when working with imported records.

## Run

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# edit .env and set DATABASE_URL to match your local PostgreSQL credentials
cd "C:\Work\AZDES\Agents\Patient Journey Orchestrator\code\backend"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The backend reads `.env` from the backend project directory, regardless of the
shell's current working directory. `DATABASE_URL` is required; the example
value may need to be updated to match your local PostgreSQL user, password,
host, and database.

Open `/docs`.

## Local authentication

Sign in at `/login` with a seeded user's email and `Test@123`. The backend
verifies the bcrypt hash and returns a JWT. Protected routes reject requests
without a valid bearer token; there is no implicit development-user bypass.

## MAQ AI

The provider is configured in `app/llm/maq_ai.py` and uses the same OpenAI-compatible pattern:

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://llm.maqsoftware.net/v1",
    api_key="sk-...",
)

resp = client.chat.completions.create(
    model="qwen-3.8-27b",
    messages=[{"role": "user", "content": "Hello, MAQ AI!"}],
)
```

The agents use this client through `app/llm/provider.py`, so the agent contracts do not depend directly on the provider implementation.

## Chatbot assistant (CarePath Assistant)

A role-aware chatbot is built into every portal as a floating widget. It uses the
same MAQ AI / OpenAI-compatible client (`app/llm/provider.py`), but the LLM never
decides permissions: every tool call is validated and executed server-side with
the requesting user's identity through the same authorization helpers and service
layer the REST API uses.

### Tools (controlled registry, `app/llm/tools.py`)

| Tool | Type | Roles | Notes |
|---|---|---|---|
| `search_patients` | read | staff | Resolve a patient by name/reference; the assistant asks which one if several match |
| `get_patient_summary` | read | staff + own patient | Patient identity + journeys |
| `list_pathways` | read | staff | Active pathway templates and steps |
| `list_journeys` | read | all (scoped) | Journeys visible to the user |
| `get_journey_steps` | read | all (scoped) | Step statuses of one journey |
| `get_pending_tasks` | read | all (scoped) | Open (pending/ready/in-progress/blocked) steps |
| `start_pathway` | **mutation** | staff | Requires confirmation; runs the same `journey_service.start_journey_for_patient` as `POST /patients/{id}/journeys` |
| `submit_event` | **mutation** | all (scoped) | Requires confirmation; same rules as the events APIs |
| `orchestrate_journey` | **mutation** | staff | Requires confirmation; re-runs the deterministic journey engine |

### Confirmation flow (server-side)

1. The LLM proposes a mutation -> the backend stores a `pending_action` on the
   assistant message with a human-readable description and a 15-minute expiry.
2. The user confirms or rejects in the chat UI (`Confirm` / `Reject` buttons or
   natural language on the next turn).
3. `POST /api/v1/chat/sessions/{sid}/messages/{mid}/confirm` re-validates
   ownership (session is scoped to the authenticated user), expiry, and role —
   then executes through the existing service layer. Results and failures are
   reported verbatim; the assistant never claims success on failure.
4. Expired proposals never execute; the user is told to ask again.

### Audit

Every chatbot event — action proposed, confirmed, executed, failed, rejected,
expired, and read-only data access — is persisted in `chat_audit_log`
(migration `migrations/20261007_add_chat_audit.sql`). Administrators can read
the trail via `GET /api/v1/chat/audit`.

### Run the chatbot tests

```powershell
cd backend
python tests_chat.py
```

Covers tool role boundaries, start_pathway business rules, the full
propose/confirm/reject/expire lifecycle, cross-user and invalid-id cases, LLM
failure handling, and REST auth boundaries. The LLM is scripted, so no MAQ AI
connectivity is required.

## Main endpoints

- `GET /api/v1/health`
- `GET /api/v1/users/me`
- `GET /api/v1/dashboard/summary`
- `GET /api/v1/patients`
- `GET /api/v1/pathways` (administrator pathway management)
- `POST /api/v1/pathways` (create an active pathway and ordered steps)
- `PUT /api/v1/pathways/{pathway_id}` (create an active edited version)
- `GET /api/v1/journeys/available-pathways` (staff)
- `POST /api/v1/patients/{patient_id}/journeys` (staff; pathway, priority, optional per-step time limits)
- `GET /api/v1/me/journeys` (signed-in patient)
- `GET /api/v1/journeys`
- `GET /api/v1/journeys/{journey_id}`
- `GET /api/v1/journeys/{journey_id}/steps`
- `POST /api/v1/journeys/{journey_id}/steps/{step_id}/complete` (staff confirmation)
- `PATCH /api/v1/journeys/{journey_id}/steps/{step_id}/time-limit`
- `GET /api/v1/journeys/{journey_id}/events`
- `POST /api/v1/journeys/{journey_id}/events`
- `POST /api/v1/journeys/{journey_id}/evaluate`
- `POST /api/v1/journeys/{journey_id}/orchestrate`
- `GET /api/v1/journeys/{journey_id}/orchestration-context`
- `GET /api/v1/exceptions`
- `PATCH /api/v1/exceptions/{exception_id}`
- `GET /api/v1/agent-runs`
- `GET /api/v1/actions/registry`
- `POST /api/v1/chat/sessions`, `GET /api/v1/chat/sessions` (chat history)
- `GET /api/v1/chat/sessions/{id}/messages`
- `POST /api/v1/chat/sessions/{id}/messages` (REST fallback for the widget)
- `POST /api/v1/chat/sessions/{sid}/messages/{mid}/confirm` / `.../reject`
- `GET /api/v1/chat/audit` (administrator)
- `WS /ws/chat?token=<JWT>` (widget transport, REST fallback)

## Important safety boundary

LLMs never directly write protected journey completion state and never execute arbitrary actions. The deterministic control plane validates dependencies, permissions, action allow-lists, idempotency, verification, and persistence.

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
- Optional AI through an environment-configured OpenAI-compatible API

All protected API routes require an email/password login and a signed bearer token. User passwords are stored as bcrypt hashes.

## Code layout

```text
backend/
  app/
    main.py             FastAPI entry point
    api/v1/              Versioned HTTP endpoints
    api/ws_chat.py       WebSocket endpoint
    auth.py              Login, password changes, and token helpers
    core/                Settings, database session, and authorization
    models/              SQLAlchemy tables, one file per table group
    schemas/             Request and response models by resource
    services/            Shared journey and chat use cases/read models
    rules/               Deterministic journey rules
    orchestration/       Event processing and agent workflow
    agents/              Supervisor, coordination, and journey intelligence
    llm/                 Model client and chat tools
    action_registry/     Supported actions and validation
    integrations/        Service protocols and local mock adapters
    audit/               Persisted audit and trace helpers
  migrations/            Ordered SQL migrations
  scripts/               Database setup and demo data tools
```

The URL version is set by `app.core.config.Settings.api_prefix`; Python route
modules remain in `app/api/v1/`. Shared read models live in `app/services/`
so staff and patient endpoints use the same representations. New code should
extend an existing module when the concern is small, and add a file when a
module has a clear independent responsibility.

## Complete Neon database setup

Create an empty database or branch in Neon, then copy its full connection URL
from the Connect dialog into `backend/.env`. Retain its SSL and connection
options. The backend accepts `postgresql://` and `postgresql+psycopg2://` URLs.
Neon connection instructions: https://neon.com/docs/get-started/connect-neon

Run from the repository root:

```powershell
python -m pip install -r backend/requirements.txt
# If backend/.env is missing, copy backend/.env.example to backend/.env first.
# Set DATABASE_URL in backend/.env to your Neon URL before continuing.
python backend/scripts/setup_database.py
```

The command creates 16 application tables, applies every SQL migration,
and seeds the 15 tables that hold demo activity: 1,200 patients, 2,400 staff/patient accounts, six
pathways, 48 template steps, 42 dependencies, 48 action rules, 1,100 journeys,
8,800 journey steps, 6,600 events, 2,200 action executions, 1,100 exceptions,
4,400 agent runs, and synthetic chat sessions, messages, and audit entries for
active users. Each patient has a linked portal account. Step time limits are
backfilled by the migrations. All demo passwords are `Test@123`, stored as
bcrypt hashes. Hash generation can take several minutes.

The setup assigns demo patients to their clinicians. Clinicians can list and
open only their assigned patients. Care coordinators see only patients granted
to them in User management. Administrators manage assignments; staff cannot
grant themselves patient access.

Schema creation, migrations, seeding, and verification share one transaction;
any failure rolls back the entire setup. The command refuses databases with
existing application data and never runs the legacy seed's delete statements.
It reads `backend/.env` regardless of the shell directory; an exported
`DATABASE_URL` takes precedence. It does not create a Neon account or project.

After setup, check the row counts without changing data:

```powershell
python backend/scripts/setup_database.py --verify-only
```

To find active demonstration login emails:

```sql
SELECT email, role FROM users WHERE is_active ORDER BY role, email LIMIT 20;
```

## Existing database

This code expects the PostgreSQL schema/seed already created for Patient Journey Orchestrator. It does **not** run `Base.metadata.create_all()` against the existing database.

Before starting this version against an existing database, apply the new migration
using a database migration account:

```powershell
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f "backend/migrations/20261012_chat_access_and_audit.sql"
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f "backend/migrations/20261013_patient_provisioning_and_pathway_roles.sql"
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f "backend/migrations/20261014_refine_clinical_pathway_workflows.sql"
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f "backend/migrations/20261019_add_journey_calendar.sql"
```

The [calendar guide](CALENDAR.md) describes calendar roles, endpoints, UTC booking
storage, planned dates, and scheduling confirmations.

The pathway migration publishes new versions of the six seeded care pathways,
assigning role owners and operational step deadlines. Completed journeys retain
their original pathway version; active journeys sync to the new version when
their steps are next loaded. Back up the database before applying data migrations.

Agent self-approval is limited to creating a coordinator follow-up task. Other
approval-gated actions remain pending for staff review.

Review and grant patient assignments in User management after migration.

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
Each ordered step has a code, name, type, details, a target day measured from
journey start, and a time allowance that begins when the step is ready. The UI
accepts hours, days, or weeks while the API stores the allowance in hours.
Administrators also select a responsible role for every step: patient,
clinician, care coordinator, administrator, or agent. Steps
created in the create form are required. Editors can change whether a step is
required. Only administrators can create or edit pathway templates.

An administrator or the assigned clinician can open **Patients → patient profile → Start a care journey**
and select an active pathway. Clinicians set priority when starting care.
Administrators have no priority control; the server starts their journeys at
`MEDIUM` until the assigned clinician changes it. Care coordinators cannot
start journeys. The person starting care can review or override each step's
time limit for that patient, then submit. The backend creates the journey and a snapshot of
its pathway steps and limits together. A step's timer starts when the step
first becomes `READY`; later steps receive an action deadline only when they
become ready. Every step also has a planned milestone date based on the target
day. Clinical staff can adjust an unfinished step's allowance from the journey
detail page. The patient sees the pathway name, planned dates, action deadlines,
and progress on **My Journey**. Clinicians can change an active journey's
priority. A patient cannot start another journey while one is active or blocked;
the start action becomes available after completion or cancellation.

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

## AI provider configuration

The optional OpenAI-compatible provider is configured only through environment
variables (or deployment secrets): `MAQ_AI_ENABLED`, `MAQ_AI_BASE_URL`,
`MAQ_AI_API_KEY`, `MAQ_AI_MODEL`, `MAQ_AI_TIMEOUT_SECONDS`, and
`MAQ_AI_MAX_RETRIES`. `MAQ_AI_TEMPERATURE` is optional. Copy
`backend/.env.example` to `backend/.env`, then fill in the provider values for
your deployment. Do not commit credentials. AI is disabled when
`MAQ_AI_ENABLED` is unset or false.

The agents use this client through `app/llm/provider.py`, so the agent contracts
do not depend directly on the provider implementation. If AI is enabled but
required provider settings are missing, client initialization reports the
missing setting instead of silently choosing a provider or model.

Network timeouts are configured in `backend/.env`: `MAQ_AI_TIMEOUT_SECONDS`,
`SMTP_TIMEOUT_SECONDS`, and `DATABASE_CONNECT_TIMEOUT_SECONDS` are specified in
seconds. The frontend API timeout is configured separately as
`VITE_API_TIMEOUT_MS` in milliseconds.

Step evidence files are stored outside the web root in
`backend/private_storage/step-evidence` by default. Set `EVIDENCE_STORAGE_DIR`
to a private, persistent volume path in deployments. The directory is excluded
from Git; it must not be served as static content. For production or real
patient data, use an encrypted, access-controlled persistent volume with
backups, and restrict downloads through the authenticated API.

## Chatbot assistant (CarePath Assistant)

A role-aware chatbot is built into every portal as a floating widget. It uses the
same MAQ AI / OpenAI-compatible client (`app/llm/provider.py`), but the LLM never
decides permissions: every tool call is validated and executed server-side with
the requesting user's identity through the same authorization helpers and service
layer the REST API uses.

### Tools (controlled registry, `app/llm/tools.py`)

Each tool is declared once as a `ToolSpec` (roles, required parameters, confirmation flag).
Read tools (`app/llm/tool_read.py`) are plain functions over DB queries scoped to the caller.
Mutating tools (`app/llm/tool_write.py`) call the same REST handlers / services the UI uses,
so step-owner rules, the patient event allowlist and admin guards cannot drift.

| Tool | Type | Roles |
|---|---|---|
| `search_patients`, `list_patients` | read | staff |
| `get_patient_summary`, `list_journeys`, `get_journey_steps`, `get_journey_events`, `get_pending_tasks` | read | all (patients: own data only) |
| `list_pathways`, `get_dashboard_summary`, `list_exceptions` | read | staff |
| `list_users`, `get_chat_audit` | read | admin |
| `start_pathway` | **mutation** | assigned clinician |
| `orchestrate_journey`, `complete_step`, `update_step_time_limit`, `update_exception` | **mutation** | staff (`complete_step` also honours the step owner's role) |
| `submit_event` | **mutation** | all (patients limited to patient event types, own journeys) |
| `submit_step_update` | **mutation** | patient |
| `set_user_role`, `set_user_status`, `create_pathway` | **mutation** | admin (cannot change own role/status from chat) |

### Request pipeline (server-side, per tool call)

1. **Role permission** - a task outside the user's role is answered with
   "You are not permitted to ...", without relying on the model to refuse.
2. **Missing information** - required parameters that are absent produce a question back to
   the user (e.g. which patient / which pathway, with the available pathways listed).
3. **Validation + scope dry-run** - ids, enums, ownership, step state and business rules are
   checked before the user is ever asked to confirm; nothing is written.
4. **Confirmation** - every mutation is stored as a `pending_action` and only runs after the user confirms.
5. **Execution** - role and scope are checked again; permission failures are reported as "not permitted".

### Confirmation flow (server-side)

1. The LLM proposes a mutation -> the backend stores a `pending_action` on the
   assistant message with a human-readable description and a 15-minute expiry.
2. The user confirms or rejects in the chat UI (`Confirm` / `Reject` buttons).
3. `POST /api/v1/chat/sessions/{sid}/messages/{mid}/confirm` re-validates
   ownership (session is scoped to the authenticated user), expiry, and role,
   then executes. Validation failures are shown to the user; unexpected
   provider or execution errors return a generic message without secrets.
4. Expired proposals never execute; the user is told to ask again.

Public signup is disabled. Administrators create patients with an optional clinician via
`POST /api/v1/admin/patients`; the temporary password appears once in the response.
Patients change it through `POST /api/v1/auth/change-password`. Administrators
create staff via `POST /api/v1/admin/users`. Existing patients can be assigned
to a clinician with `PUT /api/v1/admin/users/{user_id}/patients/{patient_id}`.
Patient lists, profiles, journeys, and calendars are limited to assigned patients
for clinicians and coordinators; patients can read only their own records.
The legacy self-claim endpoint returns 403. Clinician assignments cannot be removed or changed. The assigned clinician
starts journeys and chooses priority. Confirmations are signed for the user,
session, exact action, patient, and parameters. The backend claims each proposal
once and checks current role, patient grants, and business rules at execution.

### Audit

Chatbot decisions, validation failures, action proposals, confirmations,
executions, failures, cancellations, expirations, and read access are recorded
in `chat_audit_log`. The [20261012 migration](migrations/20261012_chat_access_and_audit.sql)
adds role, patient, correlation ID, and result status and blocks updates and
deletes with a database trigger. Only parameter names, a fingerprint, and
reference IDs are logged; clinical text and tokens are omitted. Administrators
can read the trail via `GET /api/v1/chat/audit`.

### Prompt injection safeguards

Chat rejects recognizable instructions to override or disclose its governing
prompt before a model call and omits them from older conversation history.
It also removes such instructions from retrieved
tool text; if a tool result contains one, the server returns the sanitized
result without giving the model another turn. The privileged prompt contains
only server-owned role/scope data, not the user's display name. Provider errors
are returned to clients as generic failures. Blocked attempts are recorded in
`chat_audit_log` as `prompt_injection_blocked` without the submitted text.
If audit storage is unavailable, the assistant still returns a server-written
refusal without calling the model; that turn is not saved, and the server logs
a correlation ID. Apply the audit migration to restore persisted chat history
and audit records for blocked attempts.

These checks reduce common attacks but cannot identify every malicious
paraphrase. Server-side authorization, patient scope checks, and explicit
confirmation for changes remain the security boundaries. Keep testing with
new attack examples as the chatbot and its data sources evolve.

## Orchestration agents (Orchestrate button)

`POST /journeys/{id}/orchestrate` runs the LangGraph in `app/orchestration/langgraph_supervisor.py`:
rules -> Supervisor -> (Journey Intelligence | Coordination -> Action Executor -> rules again) -> wait / escalate.

**When does a step's status change?**

| Who | When |
|---|---|
| Rule engine (every orchestrate / evaluate / event) | Pending -> Ready when earlier steps are done and dependencies are met; -> Blocked when a dependency is unmet or the step is past its due date; journey status follows. Cancelled journeys are never reopened. |
| Agent | **Only** `Completed`, and only when all hold: the step's owner is `AGENT`; it is Ready/In progress; the action ran and passed verification; the action fulfils that step type (appointment action -> appointment/follow-up step, document request -> lab/document/referral step, reminder -> reminder/education/counselling step). Otherwise the action is sent as support and the step is untouched. |
| Staff / patient | Complete steps through the UI, subject to the step owner's role. |

Other behaviour: approval-gated actions (`CREATE_COORDINATOR_TASK`) are recorded as `REQUESTED` and surfaced as an exception, never auto-run - staff **Approve / Reject** them under *Journey actions* on the journey page (`POST /api/v1/actions/{id}/approve|reject`; approving creates a real coordinator task on the Exceptions page); `ESCALATE` opens an exception for staff; the same action for the same step is never sent twice (idempotency).

**If the AI is unavailable or returns something unusable** (bad key, timeout, invalid JSON, unknown capability or action, made-up step id) the run does not fail: it continues on the built-in rules (`mode: RULES_ONLY`) and says so in the summary. The response and the saved run include `summary`, `mode`, `warnings` and `step_changes`. Saved runs use `status` SUCCESS/FAILED (DB enum); how the run ended (WAIT / ESCALATE) is `output.final_state`.

### Real patient messages (SMTP)

Reminders, document requests and appointment requests/reschedules are emailed to the patient's email on file when these are set in `backend/.env` (see `.env.example`): `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_USE_TLS`. With `SMTP_HOST` empty the actions are **simulated** and labelled "Simulated (email not configured)" everywhere in the UI. While testing, set `SMTP_REDIRECT_TO=you@example.com` so every email goes to you instead of patients (the demo data uses fake addresses). A patient with no email makes the action fail and the run escalate. Error text saved to `agent_runs` is scrubbed of API keys and tokens.

## Main endpoints

List endpoints for patients, journeys, pathways, patient journeys, journey events and actions, agent runs, exceptions, users, patient portal events, and chat sessions/messages/audit accept `limit` and `offset`. The default and maximum `limit` is 10. Responses have `items`, `total`, `limit`, and `offset`; for example, `?limit=10&offset=10` fetches the second page. `GET /api/v1/pathways` also accepts `latest_only=true` to page through the current version of each template. Dashboard summaries, the action registry, pathway selectors, and ordered journey steps remain complete views.

Search and filter parameters apply to the full set of records the caller may access before pagination. `total` counts every matching record, while `items` contains only the requested page. The chat assistant's patient, journey, exception, and user list tools follow the same rule and accept `offset` to reach later matches.

- `GET /api/v1/health`
- `GET /api/v1/users/me`
- `GET /api/v1/dashboard/summary`
- `GET /api/v1/patients`
- `GET /api/v1/pathways` (administrator pathway management)
- `POST /api/v1/pathways` (create an active pathway and ordered steps)
- `PUT /api/v1/pathways/{pathway_id}` (create an active edited version)
- `GET /api/v1/journeys/available-pathways` (staff)
- `POST /api/v1/patients/{patient_id}/journeys` (administrator or assigned clinician; clinicians supply priority, administrators omit it; optional per-step time allowances)
- `GET /api/v1/me/journeys` (signed-in patient)
- `GET /api/v1/journeys`
- `GET /api/v1/journeys/{journey_id}`
- `PATCH /api/v1/journeys/{journey_id}/priority` (assigned clinician; active or blocked journeys)
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

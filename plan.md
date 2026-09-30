# Patient Journey Orchestrator (CarePath) — Project Plan & Reference

> Single source of truth for project context, completed work, and the current task plan.
> Last updated: 2026-09-30

---

## 1. Project Overview

A healthcare **Patient Journey Orchestrator** that executes care pathways (treatment plans)
deterministically, with LLM agents assisting (never deciding state writes directly). The
frontend is a multi-portal React UI where each role sees a themed portal with role-scoped data.

### Architecture (3-Agent backend)
| Component | Location | Purpose |
|---|---|---|
| Event Processor | `backend/app/orchestration/event_processor.py` | Ingests events, idempotently |
| Deterministic control plane | `backend/app/orchestration/journey_engine.py` | Validates deps/permissions/allow-lists; only this writes journey state |
| Journey Intelligence Agent | `backend/app/agents/journey_intelligence/` | Analyzes journey context |
| Coordination Agent | `backend/app/agents/coordination/` | Plans actions |
| Supervisor Agent | `backend/app/agents/supervisor/` | LangGraph conditional supervisor loop |
| Action Registry | `backend/app/action_registry/` | Allow-list of actions agents may request |
| Rule engines | `backend/app/rules/journey_rule_engine.py`, `escalation_engine.py` | Deterministic step/escalation rules |
| LLM provider | `backend/app/llm/provider.py` → MAQ AI (`https://llm.maqsoftware.net/v1`, model `qwen-3.8-27b`) | OpenAI-compatible client |
| Audit | `backend/app/audit/` | Agent trace persistence |

**Safety boundary:** LLMs never directly write protected journey completion state and never
execute arbitrary actions. The deterministic control plane validates everything.

### Tech Stack
- **Backend:** Python / FastAPI / SQLAlchemy / PostgreSQL (source of truth) / Pydantic v2 / JWT (HS256) + bcrypt / OpenAI-compatible MAQ AI
- **Frontend:** React 19 / Vite 7 / react-router-dom 7 / axios / lucide-react icons / recharts (installed)
- **DB seeding:** `db/Create Tables.sql` + `db/patient_journey_orchestrator_seed.sql` (1,200 staff + 1,200 patient accounts, password `Test@123`)

### Run Commands
```powershell
# Backend
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # set DATABASE_URL
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Frontend
cd frontend
npm install
npm run dev              # VITE_API_BASE_URL=http://localhost:8000
```

### Environment
- `backend/.env`: `DATABASE_URL`, `AUTH_JWT_SECRET`, `AUTH_JWT_EXPIRES_MINUTES`, `CORS_ORIGINS`, `MAQ_AI_*`, `SUPERVISOR_MAX_ITERATIONS`
- `frontend/.env`: `VITE_API_BASE_URL`
- Backend reads `.env` from the backend project dir regardless of CWD. If `DEBUG` env var is non-boolean, set `$env:DEBUG = "false"`.

---

## 2. Data Model (PostgreSQL)

Schema DDL: `db/Create Tables.sql`. SQLAlchemy models: `backend/app/models/`.

| Table | Model | Key columns |
|---|---|---|
| `users` | `user.py` | id (UUID), email (unique), password_hash, display_name, **role**, **patient_id** (FK→patients, NULL for staff, unique), is_active |
| `patients` | `patient.py` | id, patient_reference, first_name, last_name, email (nullable for legacy rows), date_of_birth, gender |
| `pathways` / `pathway_steps` | `pathway.py` | code, name, version, status / step_type, sequence_number, required, due_after_days, completion_criteria (JSONB) |
| `dependencies` | `dependency.py` | pathway step dependencies |
| `journeys` | `journey.py` | patient_id, pathway_id, pathway_version, **status enum(ACTIVE, BLOCKED, COMPLETED, CANCELLED)**, **priority enum(CRITICAL, HIGH, MEDIUM, LOW)**, started_at, target_completion_at |
| `journey_steps` | `journey.py` | journey_id, pathway_step_id, **status enum(PENDING, READY, IN_PROGRESS, BLOCKED, COMPLETED, CANCELLED)**, due_at, block_reason |
| `patient_events` | `event.py` | patient_id, journey_id, event_type, source, event_time, payload (JSONB), processed |
| `pathway_action_rules` | `pathway_action_rule.py` | maps pathway steps → allowed actions |
| `action_executions` | `action_execution.py` | journey_id, action, status, requested_at |
| `exceptions` | `exception_model.py` | journey_id, **severity enum(CRITICAL, HIGH, MEDIUM, LOW)**, exception_type, title, description, **status enum(OPEN, IN_PROGRESS, RESOLVED, DISMISSED)**, recommended_action, resolved_at |
| `agent_runs` | `agent_run.py` | journey_id, agent_name, run_type, status, input_context, output, tool_calls, started_at, completed_at |

### Roles
`ADMIN` · `CLINICIAN` · `CARE_COORDINATOR` (staff) · `PATIENT` (bound 1:1 to a patient row via `users.patient_id`)

---

## 3. API Surface (`/api/v1`, all protected except `/auth/login` & `/health`)

Backend: `backend/app/api/v1/*`, wired in `app/api/router.py`. Frontend client: `frontend/src/services/api.js`.

| Endpoint | Method | Roles | Scoping |
|---|---|---|---|
| `/auth/login`, `/auth/me` | POST/GET | all | — |
| `/users/me` | GET | all | returns `{email, name, role}` |
| `/dashboard/summary` | GET | staff | `scope_patient_ids()`; admin also gets `total_users/active_users/patient_users`; returns `scope`, `role` |
| `/patients`, `/patients/{id}`, `/patients/{id}/journeys` | GET | staff | `scope_patient_ids()` filter |
| `/journeys`, `/journeys/{id}`, `/journeys/{id}/steps` | GET | staff | scoped; detail via `get_journey_scoped` (404 hides existence) |
| `/journeys/{id}/events` | GET/POST | staff | scoped; POST staff-only sources (patient-channel sources rejected) |
| `/journeys/{id}/evaluate`, `/orchestrate` | POST | staff | `get_journey_for_action` |
| `/journeys/{id}/orchestration-context` | GET | staff | scoped |
| `/journeys/{id}/actions` | GET | staff | scoped (action executions for journey) |
| `/exceptions` | GET/PATCH | staff | GET scoped; PATCH via `can_read_journey` |
| `/agent-runs` | GET | staff | global feed scoped to patient ids |
| `/actions/registry` | GET | staff | — |
| `/admin/users`, `/admin/users/{id}/role`, `/admin/users/{id}/status` | GET/PATCH | **ADMIN** | `require_admin` |
| `/me`, `/me/journeys`, `/me/journeys/{id}`, `/me/journeys/{id}/steps|events` | GET | **PATIENT** | patient resolved from token, never a request param |
| `/me/journeys/{id}/events` | POST | **PATIENT** | type + payload key allowlists, source forced to `patient-portal`, `processed=False` |

### Authorization core (`backend/app/core/authorization.py`)
- `require_staff` / `require_admin` / `require_patient` dependency gates (403)
- `can_read_journey(user, journey)` — read check; denials are **404** on read paths (no existence leak), 403 on action paths
- `scope_patient_ids(db, user)` → `None` = unrestricted (ADMIN + all staff today), `[patient_id]` for PATIENT
- Staff assignment model **does not exist yet** (TODO in code): staff scope is global by design
- Identity, role, and patient link always come from the authenticated DB user, never request bodies

---

## 4. Frontend Structure

Modular, layered architecture (see `frontend/README.md` for the annotated tree):

```
frontend/src/
├── App.jsx                    # Composition root: AuthProvider + AppRoutes (thin shell)
├── routes/                    # paths.js · guards.jsx · index.jsx (lazy route tree)
├── layouts/                   # AppLayout · portals.js · Sidebar (role chip) · Topbar
├── pages/<Feature>/index.jsx  # Folder-per-feature; private sub-components live beside
├── components/                # Shared primitives incl. TabBar (+ index barrel)
├── context/AuthContext.jsx    # token/user in localStorage, boot-time /users/me refresh
├── hooks/                     # useAsync · useTabs
├── services/                  # client.js (axios+interceptors) · one module per resource · barrel
├── utils/                     # dates · text · errors · lists · roles (+ barrel)
└── styles/                    # tokens · layout · ui · pages · portals · responsive (entry: index.css)
```

### Route guards (routes/guards.jsx)
- `/` → Dashboard (staff) or MyJourney (patient) via HomeRoute
- `/my-journey` → patient home (staff redirected back)
- `/patients*`, `/journeys*`, `/exceptions`, `/agent-runs`, `/actions` → StaffRoute
- `/users` → AdminRoute (admin only)
- UI gates are presentation-only; **the backend authorizes every API**.

### Portal theming (styles/portals.css + layout.css)
`theme-admin` (purple), `theme-clinician` (blue), `theme-coordinator` (amber), `theme-patient` (teal/light sidebar). Sidebar bottom identity card uses `.sidebar-usercard` + `.role-chip`; collapsed rail shows the initials avatar.

---

## 5. Completed Tasks (history)

### Task 1 — Initial backend + frontend first look (commit `1cd1944`)
- Full FastAPI backend: 3-agent architecture, LangGraph supervisor loop, event processor,
  deterministic journey engine, action registry + validators, mock integrations, audit/agent
  trace persistence.
- PostgreSQL schema DDL + synthetic seed (1,200 staff, 1,200 patients, journeys/steps/events).
- MAQ AI (OpenAI-compatible) LLM provider wiring.
- React/Vite frontend: login, dashboard, patients, journeys, journey detail (steps/events/
  actions/agent runs), exceptions, agent runs, action registry, user management.

### Task 2 — Role-based access control (commit `b156c91`)
- Email/password auth: bcrypt hashes (`core/passwords.py`), JWT bearer tokens (`auth.py`),
  protected routes reject anonymous requests; no dev bypass.
- RBAC service (`core/authorization.py`): `require_staff/require_admin/require_patient`,
  `can_read_journey`, `scope_patient_ids`, 404-on-read denials.
- Patient portal: `/api/v1/me/*` patient-scoped endpoints, patient-safe event submission
  (allowlists, server-forced source, unverified by default).
- Admin-only user management API (`require_admin` server-side).
- Per-role portals in the UI: themed sidebar/nav per role (`layouts/portals.js`), role
  route guards, role-specific dashboard KPIs, `utils/roles.js` capability flags.
- Dashboard scoping (`scope_patient_ids`) + admin-only user metrics.
- Patient email migration (`backend/migrations/20260930_add_patient_email.sql`) and demo
  portal seed (`backend/scripts/seed_demo_patient_portal.py`).
- RBAC test script: `backend/tests_rbac.py`.

### Task 3 — Role-based data display & portal UX (this session)
- Sidebar identity card: role chip beside the user's name, initials avatar when collapsed.
- Portal tabs: My Journey (Overview / Care plan / Updates) and role-specific Patients tabs
  (admin/clinician/coordinator variants) backed by a new `/patients?filter=` param.
- Backend enum normalization for status/priority/severity filters + PATCH exception status.
- Dashboard `recent_journeys` (scope-respecting, patient names) and journey rows enriched
  with `patient_name` / `patient_reference` / `pathway_name`.

### Task 4 — Frontend modularization (this session)
Restructured the frontend into a layered, folder-per-feature architecture:
- **services/** — split monolithic `api.js` into `client.js` (axios + interceptors) plus one
  module per resource (`auth`, `dashboard`, `patients`, `journeys`, `exceptions`, `agents`,
  `actions`, `admin`, `me`) with a barrel `index.js`.
- **utils/** — split `constants.js` by concern into `dates`, `text`, `errors`, `lists`,
  `roles` with a barrel; deleted `constants.js`.
- **routes/** — extracted from App.jsx: `paths.js` (path constants), `guards.jsx`
  (Protected/Staff/Admin/Home/Login routes), `index.jsx` (lazy-loaded route tree);
  App.jsx is now a thin composition root.
- **pages/** — every page converted to folder-per-feature (`pages/<Feature>/index.jsx`) with
  private sub-components: Dashboard (RecentJourneys, SystemPulse), MyJourney (ReportForm,
  JourneyMetrics, CarePlanPanel, UpdatesPanel, JourneyPicker), JourneyDetail (StepsTimeline,
  JourneyProgress, AddEventForm, panels), Patients (+tabs.js), Journeys (+filters.js),
  Exceptions (+filters.js), and single-file folders for the rest.
- **components/** — added shared `TabBar`; pages use `hooks/useTabs` for selection state.
- **styles/** — split the 40KB `styles.css` monolith into layers: `tokens`, `layout`, `ui`,
  `pages`, `portals`, `responsive` with a cascade-ordered `styles/index.css` entry;
  `styles.css` remains as a thin compatibility re-export.
- Routes are React.lazy code-split per page; added `RouteFallback` suspense skeleton.
- Verified: `npm run build` green; no stale imports (`utils/constants`, `services/api` gone).

---

## 6. Current Task — (none pending; last completed task is Task 4)

The role-based data display & portal UX task (Task 3) and frontend modularization (Task 4)
are complete. Future work candidates (from Task 3 notes): staff→patient assignment model,
and marking section 6 with the next task when one is chosen.

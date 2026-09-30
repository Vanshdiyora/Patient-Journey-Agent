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

For a legacy existing database, apply the migration, then add the four extra
patient portal demo records by running:

```powershell
psql -h localhost -U postgres -d patient_journey_orchestrator -f migrations/20260930_add_patient_email.sql
python scripts/seed_demo_patient_portal.py
```

If your shell has a non-boolean `DEBUG` environment variable, run
`$env:DEBUG = "false"` first so the settings loader can start.

This creates four additional synthetic patients with one journey each and
matching portal accounts. Their initial password is `Test@123`, stored as a
bcrypt hash.

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

## Main endpoints

- `GET /api/v1/health`
- `GET /api/v1/users/me`
- `GET /api/v1/dashboard/summary`
- `GET /api/v1/patients`
- `GET /api/v1/journeys`
- `GET /api/v1/journeys/{journey_id}`
- `GET /api/v1/journeys/{journey_id}/steps`
- `GET /api/v1/journeys/{journey_id}/events`
- `POST /api/v1/journeys/{journey_id}/events`
- `POST /api/v1/journeys/{journey_id}/evaluate`
- `POST /api/v1/journeys/{journey_id}/orchestrate`
- `GET /api/v1/journeys/{journey_id}/orchestration-context`
- `GET /api/v1/exceptions`
- `PATCH /api/v1/exceptions/{exception_id}`
- `GET /api/v1/agent-runs`
- `GET /api/v1/actions/registry`

## Important safety boundary

LLMs never directly write protected journey completion state and never execute arbitrary actions. The deterministic control plane validates dependencies, permissions, action allow-lists, idempotency, verification, and persistence.

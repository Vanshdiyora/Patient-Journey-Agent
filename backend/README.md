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

Authentication is intentionally optional in local development because Entra resources are not yet available. Set `AUTH_REQUIRED=true` later when Entra configuration is ready.

## Existing database

This code expects the PostgreSQL schema/seed already created for Patient Journey Orchestrator. It does **not** run `Base.metadata.create_all()` against the existing database.

The SQL seed previously supplied for this project creates the synthetic data.

## Run

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# edit .env and set DATABASE_URL to match your local PostgreSQL credentials
uvicorn app.main:app --reload
```

The backend reads `.env` from the backend project directory, regardless of the
shell's current working directory. `DATABASE_URL` is required; the example
value may need to be updated to match your local PostgreSQL user, password,
host, and database.

Open `/docs`.

## Local authentication

With `AUTH_REQUIRED=false`, the API uses the configured development user. If that user does not exist in `users`, the application creates it on startup only in development mode.

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

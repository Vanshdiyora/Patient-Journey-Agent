# CarePath Patient Journey Orchestrator — Frontend

Production-style React/Vite UI for the Patient Journey Orchestrator API.

## Run

```bash
npm install
copy .env.example .env
npm run dev
```

For macOS/Linux:

```bash
cp .env.example .env
npm install
npm run dev
```

Set:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Pages

- Overview dashboard
- Patients + patient profile
- Patient journeys + journey detail
- Journey steps / orchestration context / events / agent activity
- Exceptions with resolve action
- Agent run audit view
- Action registry
- Login / protected routes

## Backend contract

The UI follows the uploaded OpenAPI contract and calls `/api/v1/*`.

## Authentication

The UI sends email + password to:

`POST /api/v1/auth/login`

The backend verifies the stored password hash and returns a bearer token. The
Axios interceptor attaches that token to protected API calls.

## Notes

The dashboard is deliberately tolerant of a few common response envelope shapes (`items`, `patients`, `journeys`, etc.) because the uploaded OpenAPI describes some response bodies as untyped JSON.

Before production deployment:
- Replace the shared demo passwords with individual reset credentials.
- Set a strong backend JWT secret.
- Configure CORS for the deployed frontend origin.
- Set `VITE_API_BASE_URL` to the deployed API.

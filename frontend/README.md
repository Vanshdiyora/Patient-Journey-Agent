# CarePath Patient Journey Orchestrator — Frontend

Production-style React/Vite UI for the Patient Journey Orchestrator API.

## Run

Use Node.js 20.19+ or 22.12+ (required by Vite 7). Check with `node --version`.
If startup fails with `crypto.hash is not a function`, upgrade Node.js and restart
your terminal before running the commands below.

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
VITE_API_TIMEOUT_MS=300000
```

`VITE_API_TIMEOUT_MS` is the Axios request timeout in milliseconds.

## Code layout

`src/main.jsx` mounts the app and imports `styles/index.css`. `src/App.jsx` owns
providers; `src/routes/` owns path constants, access guards, and lazy page routes.
The application uses Vite and React Router; it does not use Next.js routing.

```text
frontend/src/
  components/       Shared controls; chat/ contains chat-specific UI
  context/          Application-wide auth and toast state
  features/         Feature-owned pages, UI, and API clients
  hooks/            Reusable React hooks
  layouts/          App shell and role-specific navigation
  pages/            App-level forbidden and not-found route views
  routes/           Route tree, paths, and guards
  services/         Shared Axios transport, chat socket API, public API barrel
  styles/           Ordered global CSS layers imported by index.css
  utils/            Shared helpers and role rules
```

Business route views and their feature-specific UI are grouped under
`features/<feature>/pages/` and `features/<feature>/components/` alongside their
API clients. `routes/` composes these views and retains access guards and URL
definitions. Put helpers used across features in `components/`, `hooks/`, or
`utils/`. `services/index.js` is the public API for screens;
`services/client.js` is the only Axios instance. `services/api.js` remains a
compatibility barrel, and the chat socket client remains in `services/chat.js`.
Backend authorization remains authoritative.

## Pages

- Overview dashboard (role-specific KPIs)
- Patients + patient profile (clinicians can browse all patients, filter their own and blocked care, and claim unassigned patients; administrators can create patients and assign doctors from the list or profile)
- User management (administrators create staff accounts in a side drawer)
- Patient profile journeys + journey detail
- Administrators and assigned clinicians can start care journeys; only clinicians set or update priority, and starting another journey is disabled while care is active
- Journey steps / orchestration context / events / agent activity
- Exceptions with resolve action
- Agent run audit view
- Patient portal: My Journey with Overview / Care plan / Updates tabs
- Login / protected routes / password change

The chat widget loads older messages as the conversation is scrolled upward
and more conversations as History is scrolled downward. It fetches batches of
10 through the existing chat API and preserves the visible message when older
messages arrive. Missing patient or journey details can be entered inline in
the chat, and journey orchestration changes require an in-chat Confirm or
Reject action before they run.

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

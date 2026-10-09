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

```text
frontend/src/
  components/       Small controls in ui.jsx; complex controls and chat/ separate
  context/          Auth and toast state
  hooks/            Reusable React hooks
  layouts/          App shell and role-specific navigation
  pages/            One-file routes at the top level; larger features in folders
  routes/           Route tree, paths, and guards
  services/         client.js transport, api.js resource clients, chat.js socket API
  styles/           Ordered global CSS layers imported by index.css
  utils/            Shared helpers in index.js and role rules in roles.js
```

Keep a page in one file until it has reusable or independently complex parts.
Put helpers used by several pages in `components/`, `hooks/`, or `utils/`.
`services/index.js` is the public API for screens; `services/client.js` is the
only Axios instance. API calls stay in `services/api.js`, except the chat socket
in `services/chat.js`. Backend authorization remains authoritative.

## Pages

- Overview dashboard (role-specific KPIs)
- Patients + patient profile (role-specific tabs)
- Patient journeys + journey detail
- Journey steps / orchestration context / events / agent activity
- Exceptions with resolve action
- Agent run audit view
- Action registry
- Patient portal: My Journey with Overview / Care plan / Updates tabs
- Login / protected routes

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

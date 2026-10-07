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
```

## Modular architecture

```
frontend/src/
├── main.jsx                 # ReactDOM bootstrap (BrowserRouter + App)
├── App.jsx                  # Composition root: AuthProvider + AppRoutes
├── routes/                  # Routing module
│   ├── paths.js             #   Route path constants + buildPath()
│   ├── guards.jsx           #   ProtectedRoute / StaffRoute / AdminRoute / HomeRoute
│   └── index.jsx            #   Route tree (lazy-loaded pages)
├── layouts/                 # App shell
│   ├── AppLayout.jsx        #   Shell; picks portal theme class
│   ├── portals.js           #   Per-role chrome config (nav, labels, themes)
│   ├── Sidebar.jsx          #   Collapsible rail + identity card (role chip)
│   └── Topbar.jsx           #   Breadcrumb + search + avatar
├── pages/                   # One folder per feature
│   └── <Feature>/
│       ├── index.jsx        #   Page entry (routed)
│       └── *.jsx|js         #   Private sub-components & config
├── components/              # Shared UI primitives (Panel, TabBar, MetricCard…)
├── context/AuthContext.jsx  # Session state (token + user, localStorage-backed)
├── hooks/                   # useAsync, useTabs
├── services/                # API layer: one module per backend resource
│   ├── client.js            #   Single axios instance + interceptors
│   ├── auth|patients|… .js  #   Resource clients
│   └── index.js             #   Barrel — pages import from "../services"
├── utils/                   # Pure helpers split by concern
│   ├── dates.js text.js     #   Formatters
│   ├── lists.js errors.js   #   Envelope normalizers, error extraction
│   ├── roles.js             #   Role constants + capability flags
│   └── index.js             #   Barrel
└── styles/                  # Layered CSS (imported once via styles.css)
    ├── index.css            #   Entrypoint — imports layers in cascade order
    ├── tokens.css           #   Design tokens + element resets
    ├── layout.css           #   Shell, sidebar, topbar
    ├── ui.css               #   Shared primitives (buttons, panels, tables…)
    ├── pages.css            #   Feature-page specifics
    ├── portals.css          #   Portal accent variables
    └── responsive.css       #   All media queries
```

Conventions:
- Pages import shared code through barrels (`../services`, `../utils`, `../components`).
- A page's private sub-components live next to it and are never imported by other pages.
- UI role gates are presentation-only; the backend authorizes every API.

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

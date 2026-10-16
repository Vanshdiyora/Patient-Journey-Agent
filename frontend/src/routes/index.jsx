import React, { Suspense, lazy } from "react";
import { Route, Routes } from "react-router-dom";
import AppLayout from "../layouts/AppLayout";
import Login from "../features/authentication/pages/Login";
import { PATHS } from "./paths";
import { ProtectedRoute, LoginRoute, StaffRoute, AdminRoute, HomeRoute } from "./guards";

/**
 * Route table. Pages are code-split with React.lazy so each portal only
 * downloads the bundles for the surfaces its role can reach.
 */
const Dashboard = lazy(() => import("../features/dashboard/pages/index"));
const Patients = lazy(() => import("../features/patients/pages/list/index"));
const PatientDetail = lazy(() => import("../features/patients/pages/PatientDetail"));
const Journeys = lazy(() => import("../features/journeys/pages/list/index"));
const JourneyDetail = lazy(() => import("../features/journeys/pages/detail/index"));
const Exceptions = lazy(() => import("../features/exceptions/pages/index"));
const AgentRuns = lazy(() => import("../features/agent-runs/pages/index"));
const UserManagement = lazy(() => import("../features/administration/pages/UserManagement"));
const Pathways = lazy(() => import("../features/pathways/pages/index"));
const MyJourney = lazy(() => import("../features/patient-portal/pages/index"));
const Account = lazy(() => import("../features/authentication/pages/Account"));
const Forbidden = lazy(() => import("../pages/Forbidden"));
const NotFound = lazy(() => import("../pages/NotFound"));

/** Route-level suspense fallback (full-page skeleton). */
function RouteFallback() {
  return <div className="skeleton-detail"><i /><i /><i /></div>;
}

export default function AppRoutes() {
  return (
    <Suspense fallback={<RouteFallback />}>
      <Routes>
        <Route path={PATHS.login} element={<LoginRoute><Login /></LoginRoute>} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route element={<HomeRoute />}>
              <Route index element={<Dashboard />} />
            </Route>
            <Route path={PATHS.myJourney} element={<MyJourney />} />
            <Route path={PATHS.account} element={<Account />} />
            <Route element={<StaffRoute />}>
              <Route path={PATHS.patients} element={<Patients />} />
              <Route path={PATHS.patientDetail} element={<PatientDetail />} />
              <Route path={PATHS.journeys} element={<Journeys />} />
              <Route path={PATHS.journeyDetail} element={<JourneyDetail />} />
              <Route path={PATHS.exceptions} element={<Exceptions />} />
              <Route path={PATHS.agentRuns} element={<AgentRuns />} />
              <Route element={<AdminRoute />}>
                <Route path={PATHS.pathways} element={<Pathways />} />
                <Route path={PATHS.users} element={<UserManagement />} />
              </Route>
            </Route>
          </Route>
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}

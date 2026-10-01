import React, { Suspense, lazy } from "react";
import { Route, Routes } from "react-router-dom";
import AppLayout from "../layouts/AppLayout";
import Login from "../pages/Login";
import Signup from "../pages/Signup";
import { PATHS } from "./paths";
import { ProtectedRoute, LoginRoute, StaffRoute, AdminRoute, HomeRoute } from "./guards";

/**
 * Route table. Pages are code-split with React.lazy so each portal only
 * downloads the bundles for the surfaces its role can reach.
 */
const Dashboard = lazy(() => import("../pages/Dashboard"));
const Patients = lazy(() => import("../pages/Patients"));
const PatientDetail = lazy(() => import("../pages/PatientDetail"));
const Journeys = lazy(() => import("../pages/Journeys"));
const JourneyDetail = lazy(() => import("../pages/JourneyDetail"));
const Exceptions = lazy(() => import("../pages/Exceptions"));
const AgentRuns = lazy(() => import("../pages/AgentRuns"));
const ActionRegistry = lazy(() => import("../pages/ActionRegistry"));
const UserManagement = lazy(() => import("../pages/UserManagement"));
const MyJourney = lazy(() => import("../pages/MyJourney"));
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
        <Route path={PATHS.signup} element={<LoginRoute><Signup /></LoginRoute>} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route element={<HomeRoute />}>
              <Route index element={<Dashboard />} />
            </Route>
            <Route path={PATHS.myJourney} element={<MyJourney />} />
            <Route element={<StaffRoute />}>
              <Route path={PATHS.patients} element={<Patients />} />
              <Route path={PATHS.patientDetail} element={<PatientDetail />} />
              <Route path={PATHS.journeys} element={<Journeys />} />
              <Route path={PATHS.journeyDetail} element={<JourneyDetail />} />
              <Route path={PATHS.exceptions} element={<Exceptions />} />
              <Route path={PATHS.agentRuns} element={<AgentRuns />} />
              <Route path={PATHS.actions} element={<ActionRegistry />} />
              <Route element={<AdminRoute />}>
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

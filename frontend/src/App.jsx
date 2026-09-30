import React from "react";
import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import AppLayout from "./layouts/AppLayout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Patients from "./pages/Patients";
import PatientDetail from "./pages/PatientDetail";
import Journeys from "./pages/Journeys";
import JourneyDetail from "./pages/JourneyDetail";
import Exceptions from "./pages/Exceptions";
import AgentRuns from "./pages/AgentRuns";
import ActionRegistry from "./pages/ActionRegistry";
import UserManagement from "./pages/UserManagement";
import MyJourney from "./pages/MyJourney";
import Forbidden from "./pages/Forbidden";
import NotFound from "./pages/NotFound";
import { isStaff } from "./utils/roles";

function ProtectedRoute() {
  const { token } = useAuth();
  const location = useLocation();
  return token ? <Outlet /> : <Navigate to="/login" replace state={{ from: location }} />;
}

function LoginRoute() {
  const { token } = useAuth();
  return token ? <Navigate to="/" replace /> : <Login />;
}

/** Staff-only wrapper: patients are redirected to their home page. */
function StaffRoute() {
  const { user } = useAuth();
  return isStaff(user) ? <Outlet /> : <Navigate to="/my-journey" replace />;
}

/** Admin-only wrapper. */
function AdminRoute() {
  const { user } = useAuth();
  return String(user?.role).toUpperCase() === "ADMIN" ? <Outlet /> : <Navigate to="/" replace />;
}

/** Default landing after login per role. */
function HomeRoute() {
  const { user } = useAuth();
  return isStaff(user) ? <Dashboard /> : <MyJourney />;
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginRoute />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route index element={<HomeRoute />} />
            <Route path="/my-journey" element={<MyJourney />} />
            <Route element={<StaffRoute />}>
              <Route path="/patients" element={<Patients />} />
              <Route path="/patients/:patientId" element={<PatientDetail />} />
              <Route path="/journeys" element={<Journeys />} />
              <Route path="/journeys/:journeyId" element={<JourneyDetail />} />
              <Route path="/exceptions" element={<Exceptions />} />
              <Route path="/agent-runs" element={<AgentRuns />} />
              <Route path="/actions" element={<ActionRegistry />} />
              <Route element={<AdminRoute />}>
                <Route path="/users" element={<UserManagement />} />
              </Route>
            </Route>
          </Route>
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
    </AuthProvider>
  );
}

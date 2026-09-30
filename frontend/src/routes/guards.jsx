import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { isStaff, isAdmin as isAdminRole } from "../utils/roles";
import { PATHS } from "./paths";

/**
 * Route guards — presentation-only gates. The backend authorizes every API;
 * these just keep users out of surfaces their role never uses.
 */

/** Requires a signed-in session; otherwise redirects to login. */
export function ProtectedRoute() {
  const { token } = useAuth();
  const location = useLocation();
  return token ? <Outlet /> : <Navigate to={PATHS.login} replace state={{ from: location }} />;
}

/** Signed-in users are bounced away from the login page. */
export function LoginRoute({ children }) {
  const { token } = useAuth();
  return token ? <Navigate to={PATHS.home} replace /> : children;
}

/** Staff-only wrapper: patients are redirected to their home page. */
export function StaffRoute() {
  const { user } = useAuth();
  return isStaff(user) ? <Outlet /> : <Navigate to={PATHS.myJourney} replace />;
}

/** Admin-only wrapper. */
export function AdminRoute() {
  const { user } = useAuth();
  return isAdminRole(user) ? <Outlet /> : <Navigate to={PATHS.home} replace />;
}

/** Default landing after login per role: staff dashboard vs patient journey. */
export function HomeRoute() {
  const { user } = useAuth();
  return isStaff(user) ? <Outlet /> : <Navigate to={PATHS.myJourney} replace />;
}

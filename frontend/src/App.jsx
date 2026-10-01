import { AuthProvider } from "./context/AuthContext";
import { ToastProvider } from "./context/ToastContext";
import AppRoutes from "./routes";

/**
 * App composition root: providers + route table. Routing lives in ./routes
 * (paths, guards, route tree) so this file stays a thin shell.
 */
export default function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </ToastProvider>
  );
}

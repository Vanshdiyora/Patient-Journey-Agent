import { AuthProvider } from "./context/AuthContext";
import AppRoutes from "./routes";

/**
 * App composition root: providers + route table. Routing lives in ./routes
 * (paths, guards, route tree) so this file stays a thin shell.
 */
export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Pin the dev server to 5173 so the origin matches the backend CORS allow-list.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
  },
});

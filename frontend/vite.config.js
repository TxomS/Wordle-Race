import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Local development only (npm run dev): forward /api to a backend on port 8000.
// In Docker, nginx does this job instead, so the browser always talks to one origin.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": "http://localhost:8000" },
  },
});

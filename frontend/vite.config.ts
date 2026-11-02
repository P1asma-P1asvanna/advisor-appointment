import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// In development the browser talks to Vite, and Vite forwards /api to the FastAPI server,
// so no CORS setup is needed locally. In production set VITE_API_URL (see .env.example).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: { "/api": { target: env.VITE_PROXY_TARGET || "http://localhost:8000", changeOrigin: true } },
    },
  };
});
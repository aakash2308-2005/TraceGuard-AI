import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// Vite config: dev server proxies /api to the backend to avoid CORS in dev.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY_TARGET || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Lets the dev server proxy /api straight to the backend so the frontend
      // never needs CORS configured differently per environment — just point
      // VITE_API_BASE at "" (relative) in dev and let this handle it.
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});

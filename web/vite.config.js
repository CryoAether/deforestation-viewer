import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Proxy API + tiles to FastAPI backend
      "/api": "http://localhost:8000",
      "/tiles": "http://localhost:8000",
    },
  },
});

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// dev-time proxy to FastAPI on :8000, so the frontend can call relative /documents,
// /chat, /audio, etc. paths without hardcoding a backend origin.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/documents": "http://localhost:8000",
      "/conversations": "http://localhost:8000",
      "/chat": "http://localhost:8000",
      "/ask": "http://localhost:8000",
      "/transcribe": "http://localhost:8000",
      "/audio": "http://localhost:8000",
      "/settings": "http://localhost:8000",
    },
  },
});

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En desarrollo local (npm run dev) /api y /media van al nginx de DEV ya levantado.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://localhost:8081", "/media": "http://localhost:8081", "/config.json": "http://localhost:8081" } },
  build: { sourcemap: false, assetsInlineLimit: 0 },
});

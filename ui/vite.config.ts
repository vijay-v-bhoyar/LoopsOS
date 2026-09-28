import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

const e2eIsolation = process.env.LOOPOS_E2E_ISOLATION_VERSION === "1";
const authorityProxyTarget = process.env.LOOPOS_DEV_AUTHORITY_URL?.trim() || "http://127.0.0.1:8787";

export default defineConfig({
  envDir: e2eIsolation ? false : undefined,
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: authorityProxyTarget,
        changeOrigin: false,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  test: {
    include: ["src/**/*.test.{ts,tsx}"],
    environment: "jsdom",
    environmentOptions: {
      jsdom: {
        url: "http://localhost/",
      },
    },
    setupFiles: "./src/test/setup.ts",
    globals: true,
  },
});
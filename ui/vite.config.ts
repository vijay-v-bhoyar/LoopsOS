import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

const authorityProxyTarget = process.env.LOOPOS_DEV_AUTHORITY_URL?.trim() || "http://127.0.0.1:8787";

export default defineConfig({
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

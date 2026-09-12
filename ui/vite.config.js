var _a;
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
var authorityProxyTarget = ((_a = process.env.LOOPOS_DEV_AUTHORITY_URL) === null || _a === void 0 ? void 0 : _a.trim()) || "http://127.0.0.1:8787";
export default defineConfig({
    plugins: [react()],
    server: {
        proxy: {
            "/api": {
                target: authorityProxyTarget,
                changeOrigin: false,
                rewrite: function (path) { return path.replace(/^\/api/, ""); },
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

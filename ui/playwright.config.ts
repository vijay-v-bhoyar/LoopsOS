import { defineConfig, devices } from "@playwright/test";
import { assertE2EIsolation } from "./scripts/e2e-isolation.mjs";

// Playwright loads config in an intermediate process; the live runner PID is verified from the manifest.
const run = assertE2EIsolation(process.env);

export default defineConfig({
  testDir: "./e2e",
  outputDir: run.artifactsDirectory,
  fullyParallel: false,
  workers: 2,
  timeout: 45_000,
  expect: { timeout: 8_000 },
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:4273",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    serviceWorkers: "block",
  },
  projects: [
    { name: "desktop-chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1000 } } },
    { name: "mobile-chromium", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    {
      command: "node scripts/run-python.mjs -m uvicorn loopos_authority.api:app --app-dir ../authority --host 127.0.0.1 --port 8787",
      url: "http://127.0.0.1:8787/health/ready",
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 4273 --mode e2e",
      url: "http://127.0.0.1:4273",
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
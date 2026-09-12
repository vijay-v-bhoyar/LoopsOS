import { defineConfig, devices } from "@playwright/test";

const externalServers = process.env.LOOPOS_E2E_EXTERNAL_SERVERS === "1";
const configuredWorkers = Number.parseInt(process.env.LOOPOS_E2E_WORKERS ?? "2", 10);
const workerCount = Number.isInteger(configuredWorkers) && configuredWorkers > 0 ? configuredWorkers : 2;

export default defineConfig({
  testDir: "./e2e",
  outputDir: "../output/playwright/test-results",
  fullyParallel: false,
  // Keep the default matrix below the mobile-browser context limit; override when capacity is known.
  workers: workerCount,
  timeout: 45_000,
  expect: { timeout: 8_000 },
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:4273",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop-chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1000 } } },
    { name: "mobile-chromium", use: { ...devices["Pixel 7"] } },
  ],
  webServer: externalServers ? undefined : [
    {
      command: "node scripts/run-python.mjs -m uvicorn loopos_authority.api:app --app-dir ../authority --host 127.0.0.1 --port 8787",
      url: "http://127.0.0.1:8787/health/ready",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: "node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 4273",
      url: "http://127.0.0.1:4273",
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});

import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  outputDir: "../output/playwright/test-results",
  fullyParallel: false,
  workers: 4,
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
  webServer: [
    {
      command: "python -m uvicorn loopos_authority.api:app --app-dir ../authority --host 127.0.0.1 --port 8787",
      url: "http://127.0.0.1:8787/health/ready",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 4273",
      url: "http://127.0.0.1:4273",
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});

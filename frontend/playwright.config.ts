import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  testMatch: process.env.ROADPULSE_LIVE_E2E === "1" ? ["live-camera.spec.ts"] : ["smoke.spec.ts", "source-selection.spec.ts", "real-source.spec.ts"],
  timeout: 65000,
  expect: { timeout: 10000 },
  fullyParallel: false,
  reporter: "list",
  use: { baseURL: "http://127.0.0.1:5173", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command:
        "../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log",
      cwd: "../backend",
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer:
        !process.env.CI && process.env.ROADPULSE_REAL_E2E !== "1" && process.env.ROADPULSE_LIVE_E2E !== "1",
      env: {
        ROADPULSE_CAMERA_MODE: "replay",
        ROADPULSE_DIGITRAFFIC_ENABLED:
          process.env.ROADPULSE_REAL_E2E === "1" ? "true" : "false",
        ROADPULSE_MODEL_PATH: "../runtime/models/yolo11n.pt",
        ROADPULSE_CAMERA_URL: "",
        ROADPULSE_REPLAY_PATH: "",
        ROADPULSE_DATABASE_URL: "sqlite:///../runtime/e2e.db",
      },
    },
    {
      command: "npm run dev -- --port 5173 --strictPort",
      url: "http://127.0.0.1:5173",
      reuseExistingServer:
        !process.env.CI && process.env.ROADPULSE_REAL_E2E !== "1" && process.env.ROADPULSE_LIVE_E2E !== "1",
    },
  ],
});

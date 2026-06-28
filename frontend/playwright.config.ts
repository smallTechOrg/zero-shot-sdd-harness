import { defineConfig, devices } from '@playwright/test'

// E2E config for the Local Data Analyst frontend.
// Runs against the LIVE app served by FastAPI at http://localhost:8001/app/.
// The server is started by the gate runner (agent-builder), NOT by this config.
export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60_000,
  fullyParallel: false,
  reporter: 'line',
  use: {
    baseURL: 'http://localhost:8001',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})

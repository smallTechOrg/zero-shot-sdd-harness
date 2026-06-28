import { defineConfig, devices } from '@playwright/test'

// E2E drives the LIVE app served by FastAPI at http://localhost:8001/app/.
// The phase gate boots the backend (`uv run python -m src`) and builds/serves
// the static export before running these tests, so we do NOT start a webServer
// here — we assume the server is already up.
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [['list']],
  timeout: 120_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: 'http://localhost:8001/app/',
    trace: 'on-first-retry',
    actionTimeout: 15_000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})

import { defineConfig, devices } from '@playwright/test'

// E2E runs against the live single-origin server: `uv run python -m src`
// serving the static export at http://localhost:8001/app/.
export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  retries: 0,
  reporter: 'line',
  use: {
    baseURL: 'http://localhost:8001/app/',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})

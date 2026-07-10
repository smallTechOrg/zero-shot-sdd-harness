import { defineConfig, devices } from '@playwright/test'

// The webServer command is exactly the documented run command; it serves the
// built frontend at /app and the API at /api on a single origin. Real Gemini
// runs take 30–90 s, hence the generous test timeout.
export default defineConfig({
  testDir: 'tests/e2e',
  timeout: 240_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: 'line',
  use: {
    baseURL: 'http://localhost:8001',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'uv run python -m src',
    url: 'http://localhost:8001/health',
    timeout: 90_000,
    reuseExistingServer: true,
  },
})

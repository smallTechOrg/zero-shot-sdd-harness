import { defineConfig, devices } from '@playwright/test'

// E2E smoke for the Local Data Analyst primary journey, run against the LIVE
// app: the FastAPI server serves the built Next.js static export at /app/ and
// also exposes the real API + real Gemini (keys from repo-root .env) + real
// DuckDB. There is NO mocking here — this proves the whole stack end to end.
//
// Prerequisite: the static export must be built first (`pnpm build` produces
// frontend/out/). The phase gate runs `pnpm build` before `playwright test`,
// so we assume frontend/out/ already exists. The `webServer` below boots the
// Python backend (`uv run python -m src` from the repo root, cwd: '..') which
// mounts frontend/out/ at /app/. If a server is already running on :8001 we
// reuse it (handy for local iteration).
export default defineConfig({
  testDir: './tests/e2e',
  // The real model + DuckDB run can take tens of seconds; be generous.
  timeout: 120_000,
  expect: { timeout: 90_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:8001/app/',
    trace: 'retain-on-failure',
    actionTimeout: 90_000,
    navigationTimeout: 60_000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    // Boot the real backend from the repo root. It mounts the built static
    // export at /app/ and serves the real API. Reuse an already-running
    // instance if present.
    command: 'uv run python -m src',
    cwd: '..',
    url: 'http://localhost:8001/health',
    reuseExistingServer: true,
    timeout: 120_000,
    stdout: 'pipe',
    stderr: 'pipe',
  },
})

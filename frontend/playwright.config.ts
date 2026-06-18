import { defineConfig } from "@playwright/test";

// Single-process E2E: FastAPI serves both the API and the exported UI on :8001.
// The UI must be built first (npm run build → frontend/out). The backend needs the Gemini key.
export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: { baseURL: "http://localhost:8001", trace: "on-first-retry" },
  webServer: {
    command:
      "cd .. && DATA_ANALYST_DATABASE_URL=sqlite+aiosqlite:///./datachat_e2e.db " +
      "DATA_ANALYST_DUCKDB_DIR=.duckdb_e2e uv run python -m datachat",
    url: "http://localhost:8001/health",
    timeout: 60_000,
    reuseExistingServer: !process.env.CI,
  },
});

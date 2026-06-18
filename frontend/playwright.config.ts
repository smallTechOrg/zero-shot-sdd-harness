import { defineConfig } from "@playwright/test";

// Drives the real stack: the FastAPI backend (8001, real Gemini) + the Next.js app (3000).
// Both servers are started by webServer below; the backend needs DATA_ANALYST_GEMINI_API_KEY set.
export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: { baseURL: "http://localhost:3100", trace: "on-first-retry" },
  webServer: [
    {
      command:
        "cd .. && DATA_ANALYST_DATABASE_URL=sqlite+aiosqlite:///./datachat_e2e.db " +
        "DATA_ANALYST_DUCKDB_DIR=.duckdb_e2e DATA_ANALYST_CORS_ORIGINS=http://localhost:3100 " +
        "uv run python -m datachat",
      url: "http://localhost:8001/health",
      timeout: 60_000,
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "npm run start -- -p 3100",
      url: "http://localhost:3100",
      timeout: 60_000,
      reuseExistingServer: !process.env.CI,
    },
  ],
});

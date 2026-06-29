import { test, expect } from "@playwright/test";
import * as path from "path";
import * as fs from "fs";
import * as os from "os";

const BASE_URL = "http://localhost:8001/app";

// Create a test CSV file
function createTestCsv(): string {
  const tmpFile = path.join(os.tmpdir(), `test_${Date.now()}.csv`);
  const content = `region,revenue,units
West,12500,120
East,8750,85
North,6200,62
South,9800,98
West,14200,140
`;
  fs.writeFileSync(tmpFile, content);
  return tmpFile;
}

test.describe("Phase 1 — CSV Analysis Agent", () => {
  test("page loads and shows upload dropzone", async ({ page }) => {
    await page.goto(BASE_URL);
    await expect(page.locator("text=Drop a CSV file here")).toBeVisible({ timeout: 10000 });
    await expect(page.locator("text=CSV only")).toBeVisible();
  });

  test("upload CSV shows profile card", async ({ page }) => {
    const csvPath = createTestCsv();
    try {
      await page.goto(BASE_URL);
      await page.waitForSelector("text=Drop a CSV file here");

      // Upload via file input
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(csvPath);

      // Wait for profile card
      await expect(page.locator("text=5 rows")).toBeVisible({ timeout: 15000 });
      await expect(page.locator("text=3 columns")).toBeVisible();
      await expect(page.locator("text=region")).toBeVisible();
      await expect(page.locator("text=revenue")).toBeVisible();
    } finally {
      fs.unlinkSync(csvPath);
    }
  });

  test("upload CSV and ask a text question", async ({ page }) => {
    const csvPath = createTestCsv();
    try {
      await page.goto(BASE_URL);
      await page.waitForSelector("text=Drop a CSV file here");

      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(csvPath);
      await expect(page.locator("text=5 rows")).toBeVisible({ timeout: 15000 });

      // Ask a question
      const textarea = page.locator("textarea");
      await textarea.fill("What is the total revenue?");
      await page.locator("button:has-text('Send')").click();

      // User message appears immediately
      await expect(page.locator("text=What is the total revenue?")).toBeVisible();

      // Wait for assistant response (real LLM call — may take up to 45s)
      await expect(page.locator('[class*="justify-start"] p').first()).not.toBeEmpty({ timeout: 45000 });
    } finally {
      fs.unlinkSync(csvPath);
    }
  });

  test("shows Phase 2 stubs as disabled", async ({ page }) => {
    const csvPath = createTestCsv();
    try {
      await page.goto(BASE_URL);
      await page.waitForSelector("text=Drop a CSV file here");
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(csvPath);
      await expect(page.locator("text=5 rows")).toBeVisible({ timeout: 15000 });

      // Phase 2 stubs must be visible but disabled
      await expect(page.locator("button:has-text('Export Data')")).toBeDisabled();
      await expect(page.locator("button:has-text('Upload another file')")).toBeDisabled();
    } finally {
      fs.unlinkSync(csvPath);
    }
  });
});

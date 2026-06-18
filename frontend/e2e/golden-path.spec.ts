import { expect, test } from "@playwright/test";

// End-to-end through the real stack: browser → Next.js → FastAPI → ReAct agent (real Gemini)
// → DuckDB → back. Asserts the post-JavaScript DOM: answer text, result table, and a chart.
test("upload a CSV, ask for a chart, see answer + table + chart", async ({ page }) => {
  const unique = `E2E Sales ${Date.now()}`;

  await page.goto("/");

  // Create a dataset
  await page.getByTestId("new-dataset-name").fill(unique);
  await page.getByTestId("create-dataset").click();

  // It becomes selected; upload a CSV
  const csv = "region,sales\nwest,100\neast,200\nnorth,150\nsouth,50\n";
  await page.getByTestId("file-input").setInputFiles({
    name: "sales.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(csv),
  });

  // The file summary appears once upload completes
  await expect(page.getByText(/sales\.csv — 4 rows/)).toBeVisible({ timeout: 30_000 });

  // Ask a question that should produce a chart
  await page.getByTestId("question-input").fill("Show total sales by region as a bar chart.");
  await page.getByTestId("send").click();

  // An assistant answer bubble appears (real Gemini run)
  const assistant = page.getByTestId("msg-assistant").first();
  await expect(assistant).toBeVisible({ timeout: 90_000 });
  await expect(assistant).toContainText(/\d/); // some number in the answer

  // The result table rendered
  await expect(page.getByTestId("result-table").first()).toBeVisible();

  // The chart rendered (Recharts emits an <svg> inside the chart container)
  const chart = page.getByTestId("chart").first();
  await expect(chart).toBeVisible();
  await expect(chart.locator("svg")).toBeVisible();
});

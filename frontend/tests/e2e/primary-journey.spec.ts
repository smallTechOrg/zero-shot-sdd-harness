import { expect, test } from '@playwright/test'
import path from 'node:path'

// Resolve the fixture relative to this file (works regardless of cwd).
// Playwright transpiles specs to CommonJS, so __dirname is available here.
const CSV_FIXTURE = path.resolve(__dirname, '../fixtures/sales.csv')

// The full Phase-1 primary journey against the LIVE app (real Gemini via .env,
// real DuckDB, real SQLite). Every step asserts REAL rendered content, not just
// a 200 — a page that loads but shows nothing must FAIL this test.
test('upload -> profile -> ask -> answer + chart + table + show-its-work', async ({ page }) => {
  // ---------------------------------------------------------------------------
  // 1. Page loads, renders the Analyst screen, and is actually styled.
  // ---------------------------------------------------------------------------
  await page.goto('/app/')

  await expect(page.getByRole('heading', { name: 'Local Data Analyst' })).toBeVisible()
  await expect(page.getByTestId('uploader')).toBeVisible()
  await expect(page.getByTestId('sidebar')).toBeVisible()

  // Proves the CSS bundle loaded (not a bare unstyled page): the centered main
  // has a real max-width applied and the heading uses a non-default weight.
  const mainMaxWidth = await page
    .locator('main')
    .evaluate((el) => getComputedStyle(el).maxWidth)
  expect(mainMaxWidth).not.toBe('none')
  const headingWeight = await page
    .getByRole('heading', { name: 'Local Data Analyst' })
    .evaluate((el) => getComputedStyle(el).fontWeight)
  expect(Number(headingWeight)).toBeGreaterThanOrEqual(600)

  // Empty state is shown before any upload.
  await expect(page.getByTestId('empty-state')).toBeVisible()

  // ---------------------------------------------------------------------------
  // 2. Upload the CSV -> the REAL DuckDB profile card appears.
  // ---------------------------------------------------------------------------
  await page.getByTestId('file-input').setInputFiles(CSV_FIXTURE)

  const profile = page.getByTestId('profile-card')
  await expect(profile).toBeVisible({ timeout: 60_000 })

  // Real row count + column count badge (e.g. "600 rows · 4 columns").
  await expect(profile).toContainText(/\d[\d,]*\s+rows/)
  await expect(profile).toContainText(/\d+\s+columns/)

  // Real column names from the fixture, each with an inferred DuckDB type.
  await expect(profile.getByRole('cell', { name: 'region', exact: true })).toBeVisible()
  await expect(profile.getByRole('cell', { name: 'sales', exact: true })).toBeVisible()
  // A type chip (DuckDB types are upper-case, e.g. VARCHAR / DOUBLE / BIGINT).
  await expect(profile.locator('td span.font-mono').first()).toContainText(/[A-Z]/)

  // The sidebar's "current dataset" is now REAL (not the greyed stub).
  await expect(page.getByTestId('current-dataset')).toContainText('sales.csv')

  // ---------------------------------------------------------------------------
  // 3. Ask a real natural-language question.
  // ---------------------------------------------------------------------------
  await expect(page.getByTestId('ask-box')).toBeVisible()
  await page.getByTestId('question-input').fill('Which region had the highest total sales?')
  await page.getByTestId('ask-button').click()

  // The agent (real Gemini + DuckDB) can take tens of seconds. Wait for the
  // answer panel and assert it did NOT fail.
  const answerPanel = page.getByTestId('answer-panel')
  await expect(answerPanel).toBeVisible({ timeout: 90_000 })

  // A transport-level error (network / 404 / 422) must not have occurred.
  await expect(page.getByTestId('ask-error')).toHaveCount(0)
  // The agent must have completed, not returned status:"failed".
  await expect(page.getByTestId('answer-failed')).toHaveCount(0)
  const answer = page.getByTestId('answer-success')
  await expect(answer).toBeVisible()

  // ---------------------------------------------------------------------------
  // 4. Assert REAL output: a non-empty answer, a summary table with rows, and a
  //    chart (or, acceptably, a table-only fallback).
  // ---------------------------------------------------------------------------
  // Non-empty answer prose (the paragraph after the "Answer" heading).
  const answerText = (await answer.locator('p').first().innerText()).trim()
  expect(answerText.length).toBeGreaterThan(15)

  // A summary table with at least one data row of real values.
  const summaryTable = page.getByTestId('summary-table')
  await expect(summaryTable).toBeVisible()
  const dataRows = summaryTable.locator('tbody tr')
  expect(await dataRows.count()).toBeGreaterThan(0)
  // First body cell carries a real (non-placeholder) value.
  const firstCell = (await summaryTable.locator('tbody tr td').first().innerText()).trim()
  expect(firstCell.length).toBeGreaterThan(0)
  expect(firstCell).not.toBe('—')

  // A chart (Recharts -> svg) OR an explicit table-only fallback. Either proves
  // real content; we just require one of the two visualisation paths.
  const chart = page.getByTestId('chart')
  const chartCount = await chart.count()
  if (chartCount > 0) {
    await expect(chart.locator('svg').first()).toBeVisible()
  } else {
    // Table-only fallback is acceptable; the summary table above is the proof.
    expect(await summaryTable.count()).toBeGreaterThan(0)
  }

  // ---------------------------------------------------------------------------
  // 5. Expand "Show its work" -> plan + trace + the exact DuckDB SQL are REAL.
  // ---------------------------------------------------------------------------
  await page.getByTestId('show-its-work-toggle').click()
  const work = page.getByTestId('work-detail')
  await expect(work).toBeVisible()

  // The executed SQL is shown and is real DuckDB SQL (a SELECT over the table).
  const sql = page.getByTestId('executed-sql')
  await expect(sql).toBeVisible()
  await expect(sql).toContainText(/select/i)

  // The step trace lists the agent's steps (plan / execute / phrase ...).
  await expect(work).toContainText('Step trace')
  const traceSteps = work.locator('ul li')
  expect(await traceSteps.count()).toBeGreaterThan(0)
  await expect(work).toContainText('Plan')

  // Per-question cost is REAL (a $ figure in the toggle header).
  await expect(page.getByTestId('cost-usd')).toContainText('$')

  // ---------------------------------------------------------------------------
  // 6. At least one labelled STUB is visibly a stub (greyed + "coming soon"),
  //    so a stub is never mistaken for a bug or for real output.
  // ---------------------------------------------------------------------------
  const stubBadges = page.getByTestId('stub-badge')
  expect(await stubBadges.count()).toBeGreaterThan(0)
  await expect(stubBadges.first()).toContainText(/coming soon/i)

  // The daily-cost roll-up stub shows the placeholder dash (distinct from the
  // REAL per-question cost asserted above).
  await expect(page.getByTestId('daily-cost')).toHaveText('—')
})

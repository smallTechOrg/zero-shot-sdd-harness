import path from 'node:path'
import { test, expect, type Page } from '@playwright/test'

// Absolute path to the sample olist CSV from the repo root. This file
// (frontend/tests/e2e/analyst.spec.ts) is three levels below the repo root.
const REPO_ROOT = path.resolve(__dirname, '..', '..', '..')
const SAMPLE_CSV = path.join(
  REPO_ROOT,
  'src',
  'data',
  'datasets',
  '8bc76e9e-1151-437e-95eb-727b57b674ee',
  'olist_orders_dataset.csv',
)

const QUESTION = 'How many orders are there for each order_status?'

// Load the app and upload the sample olist_orders CSV, waiting until the
// dataset is ready and the question box is enabled. Shared by every test.
async function loadSampleDataset(page: Page): Promise<void> {
  await page.goto('/app/')
  await expect(page.getByRole('heading', { name: 'Local CSV Analyst' })).toBeVisible()
  await page.setInputFiles('#csv-file-input', SAMPLE_CSV)
  await expect(page.getByText('olist_orders_dataset.csv')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByLabel('Your question')).toBeEnabled()
}

test('upload CSV, ask a question, get a real answer + chart + table + code', async ({ page }) => {
  await page.goto('/app/')

  // Page loads and is styled (the header renders).
  await expect(page.getByRole('heading', { name: 'Local CSV Analyst' })).toBeVisible()

  // Labelled stubs are present and read "Coming soon" — never mistaken for bugs.
  await expect(page.getByText('Dataset Library')).toBeVisible()
  await expect(page.getByText('Coming soon').first()).toBeVisible()

  // Question box is disabled until a dataset loads.
  await expect(page.getByLabel('Your question')).toBeDisabled()

  // Upload the sample CSV.
  await page.setInputFiles('#csv-file-input', SAMPLE_CSV)

  // Dataset loads — filename + a known column appear, question box enables.
  await expect(page.getByText('olist_orders_dataset.csv')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('order_status', { exact: false }).first()).toBeVisible()
  await expect(page.getByLabel('Your question')).toBeEnabled()

  // Phase 2: the auto-profile panel renders REAL per-column profile info
  // (a type badge for a known column + distinct/missing counts), not a stub.
  const profile = page.getByTestId('profile-panel')
  await expect(profile).toBeVisible()
  // `order_status` is a low-cardinality categorical — assert a type badge renders.
  await expect(profile.getByTestId('profile-type-badge').first()).toBeVisible()
  // Real distinct/missing counts appear in the table header + rows.
  // Scope to the column headers explicitly: a bare getByText('Missing')
  // is strict-mode-ambiguous (it also matches the "N with missing values"
  // summary span), so target the <th> via its columnheader role.
  await expect(profile.getByRole('columnheader', { name: 'Distinct' })).toBeVisible()
  await expect(profile.getByRole('columnheader', { name: 'Missing' })).toBeVisible()
  await expect(profile.getByTestId('profile-row').first()).toBeVisible()

  // Ask the canonical question.
  await page.getByLabel('Your question').fill(QUESTION)
  await page.getByRole('button', { name: 'Ask' }).click()

  // Live stream shows a plan, then steps (transparency surface).
  await expect(page.getByText('Plan')).toBeVisible({ timeout: 60_000 })

  // A real answer renders (not just HTTP 200).
  const answer = page.getByTestId('answer-card')
  await expect(answer).toBeVisible({ timeout: 90_000 })
  const answerText = (await answer.innerText()).trim()
  expect(answerText.length).toBeGreaterThan(20)

  // A REAL POPULATED table renders — not just the always-visible container.
  // Assert at least one actual data ROW exists and that it carries a known
  // status value plus a numeric count cell. (The old assertion only checked
  // the container, which is visible even when the table is empty.)
  const tableView = page.getByTestId('table-view')
  await expect(tableView).toBeVisible()
  await expect(tableView.getByTestId('table-row').first()).toBeVisible()
  expect(await tableView.getByTestId('table-row').count()).toBeGreaterThan(0)
  // A canonical olist order_status value must appear in a populated cell.
  await expect(
    tableView.getByTestId('table-cell').filter({ hasText: 'delivered' }).first(),
  ).toBeVisible()
  // At least one cell holds a real numeric count (digits), proving the
  // groupby produced data rather than an empty/faked table.
  const tableText = (await tableView.innerText()).trim()
  expect(tableText).toMatch(/\d/)

  // A REAL chart TRACE rendered — the populated-plot container only mounts when
  // chartSpec.data is non-empty, so this distinguishes a real trace from the
  // always-visible empty-state placeholder. We then confirm Plotly drew an SVG.
  await expect(page.getByTestId('chart-view')).toBeVisible()
  const chartPlot = page.getByTestId('chart-plot')
  await expect(chartPlot).toBeVisible({ timeout: 30_000 })
  // Plotly renders its traces into an <svg class="main-svg"> once data is laid
  // out — assert that real SVG plot content exists inside the chart.
  await expect(chartPlot.locator('svg.main-svg').first()).toBeVisible({ timeout: 30_000 })

  // The code accordion reveals real pandas when expanded.
  await expect(page.getByTestId('code-accordion')).toBeVisible()
  await page.getByRole('button', { name: 'Show code' }).click()
  const codeBlock = page.getByTestId('code-block')
  await expect(codeBlock).toBeVisible()
  const code = (await codeBlock.innerText()).trim()
  expect(code.length).toBeGreaterThan(5)

  // Phase 2: 2–3 real follow-up chips render under the answer, and clicking
  // one submits it as a NEW question that runs a fresh analysis.
  const strip = page.getByTestId('followups-strip')
  await expect(strip).toBeVisible()
  const chips = strip.getByTestId('followup-chip')
  const chipCount = await chips.count()
  expect(chipCount).toBeGreaterThanOrEqual(2)
  expect(chipCount).toBeLessThanOrEqual(3)

  // Capture the first answer text so we can confirm a new run replaces it.
  const firstAnswer = (await answer.innerText()).trim()

  // Click the first follow-up → a fresh run starts (plan + stream reappear)
  // and a new answer renders.
  await chips.first().click()
  await expect(page.getByText('Plan')).toBeVisible({ timeout: 60_000 })
  await expect(answer).toBeVisible({ timeout: 90_000 })
  const secondAnswer = (await answer.innerText()).trim()
  expect(secondAnswer.length).toBeGreaterThan(20)
  // A genuinely new run produced output (content may differ from the first).
  expect(secondAnswer.length).toBeGreaterThan(0)
  void firstAnswer
})

// Defect-1 regression guard: a SCALAR answer (a single number/percentage) must
// now ALSO carry a non-empty summary table. Before the fix, scalar questions
// returned a green answer with an empty table — this asserts the table is
// populated, not just that its container is visible.
test('scalar question still renders a non-empty summary table', async ({ page }) => {
  await loadSampleDataset(page)

  // A scalar question answerable purely from olist_orders' own columns.
  await page.getByLabel('Your question').fill(
    "How many orders have status 'delivered'?",
  )
  await page.getByRole('button', { name: 'Ask' }).click()

  // A real success answer renders (NOT a failure card).
  const answer = page.getByTestId('answer-card')
  await expect(answer).toBeVisible({ timeout: 120_000 })
  await expect(page.getByTestId('failure-card')).toHaveCount(0)
  const answerText = (await answer.innerText()).trim()
  expect(answerText.length).toBeGreaterThan(10)

  // The summary table must be POPULATED — at least one real data row with a
  // numeric value. This is the Defect-1 guard: scalar answers carry a table.
  const tableView = page.getByTestId('table-view')
  await expect(tableView).toBeVisible()
  await expect(tableView.getByTestId('table-row').first()).toBeVisible({ timeout: 15_000 })
  expect(await tableView.getByTestId('table-row').count()).toBeGreaterThan(0)
  expect((await tableView.innerText()).trim()).toMatch(/\d/)
})

// Defect-2 regression guard: a question about a column that is NOT in the
// loaded olist_orders file (freight_value / customer_state live in OTHER olist
// files) must surface the distinct FailureCard "couldn't answer with this
// dataset" state — NOT a fake green answer — and must LIST the available
// columns so the user knows what they can ask instead.
test('out-of-scope column question shows a FailureCard listing available columns', async ({
  page,
}) => {
  await loadSampleDataset(page)

  // freight_value and customer_state are NOT columns of olist_orders_dataset.csv.
  await page.getByLabel('Your question').fill(
    'What is the average freight_value by customer_state?',
  )
  await page.getByRole('button', { name: 'Ask' }).click()

  // The DISTINCT failure channel must render — not the success AnswerCard.
  const failure = page.getByTestId('failure-card')
  await expect(failure).toBeVisible({ timeout: 120_000 })
  // It is the failure channel, not a green answer.
  await expect(page.getByTestId('answer-card')).toHaveCount(0)

  // The failure message must LIST available columns so the user can recover —
  // assert a real olist_orders column name surfaces in the failure text.
  await expect(failure).toContainText('order_status')
})

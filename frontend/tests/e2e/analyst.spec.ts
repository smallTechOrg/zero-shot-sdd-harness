import path from 'node:path'
import { test, expect } from '@playwright/test'

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

  // The chart container renders.
  await expect(page.getByTestId('chart-view')).toBeVisible()

  // The table renders.
  await expect(page.getByTestId('table-view')).toBeVisible()

  // The code accordion reveals real pandas when expanded.
  await expect(page.getByTestId('code-accordion')).toBeVisible()
  await page.getByRole('button', { name: 'Show code' }).click()
  const codeBlock = page.getByTestId('code-block')
  await expect(codeBlock).toBeVisible()
  const code = (await codeBlock.innerText()).trim()
  expect(code.length).toBeGreaterThan(5)
})

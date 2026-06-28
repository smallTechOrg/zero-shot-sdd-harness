import { test, expect } from '@playwright/test'
import path from 'node:path'

const FIXTURE_CSV = path.join(__dirname, 'fixtures', 'orders-small.csv')

// Phase 1 E2E — drives the LIVE app served by FastAPI at /app/.
// Asserts on CONTENT (headings, control text, stub labels) and the primary
// journey: page loads styled → upload a CSV → ask a question → real answer
// with result table, Plan, Code, and Cost chip renders.

test.describe('Phase 1 — Personal Data Analyst', () => {
  test('page loads styled with the primary controls and labelled stubs', async ({ page }) => {
    await page.goto('/app/')

    // Real heading.
    await expect(page.getByRole('heading', { name: 'Personal Data Analyst' })).toBeVisible()

    // The page is actually styled (not raw HTML): header has a white background.
    const header = page.locator('header')
    await expect(header).toBeVisible()
    const bg = await header.evaluate(el => getComputedStyle(el).backgroundColor)
    expect(bg).not.toBe('rgba(0, 0, 0, 0)')

    // Primary controls present.
    await expect(page.getByRole('button', { name: 'Upload CSV' })).toBeVisible()
    await expect(page.getByLabel('Ask a question about your data')).toBeVisible()

    // Question box is disabled until a dataset is loaded.
    await expect(page.getByRole('button', { name: 'Ask' })).toBeDisabled()

    // Labelled stubs are present and obviously deliberate.
    await expect(page.getByText('Library & History')).toBeVisible()
    await expect(page.getByText('File library')).toBeVisible()
    await expect(page.getByText('Question history')).toBeVisible()
    const comingSoon = page.getByText(/Coming soon/i)
    expect(await comingSoon.count()).toBeGreaterThan(0)
  })

  test('upload a CSV → ask a question → real answer with table, plan, code, cost', async ({
    page,
  }) => {
    test.setTimeout(90_000)
    await page.goto('/app/')

    // Upload the fixture CSV (the hidden input drives POST /datasets).
    await page.getByTestId('file-input').setInputFiles(FIXTURE_CSV)

    // Active-dataset bar shows the filename + counts.
    await expect(page.getByTestId('active-filename')).toHaveText('orders-small.csv', {
      timeout: 30_000,
    })
    await expect(page.getByText(/rows/)).toBeVisible()
    await expect(page.getByText(/cols/)).toBeVisible()

    // Fill the question first — the Ask button is intentionally disabled until
    // the textarea is non-empty (good UX), so assert "enabled" only after typing.
    await page
      .getByLabel('Ask a question about your data')
      .fill('What is the total revenue by region, highest first?')

    // QuestionBox is now enabled (dataset loaded + question typed).
    const ask = page.getByRole('button', { name: 'Ask' })
    await expect(ask).toBeEnabled()

    // Ask the real question (runs the real agent on the live backend).
    await ask.click()

    // Real answer renders (not a spinner / error).
    const answerPanel = page.getByTestId('answer-panel')
    // POST /questions hits real Gemini and can take ~30s; allow generous time.
    await expect(answerPanel).toBeVisible({ timeout: 60_000 })
    await expect(page.getByTestId('loading-state')).toHaveCount(0)
    await expect(page.getByTestId('error-state')).toHaveCount(0)

    // A REAL answer: the analysis did not fail and the answer text is non-empty.
    await expect(page.getByTestId('failed-state')).toHaveCount(0)
    const answerText = page.getByTestId('answer-text')
    await expect(answerText).toBeVisible()
    await expect(answerText).not.toHaveText('')

    // Cost chip is always present on a completed answer.
    await expect(page.getByTestId('cost-chip')).toBeVisible()

    // Plan and Code collapsibles are present.
    await expect(page.getByTestId('plan-view')).toBeVisible()
    await expect(page.getByTestId('code-view')).toBeVisible()

    // The generated code is viewable when expanded.
    await page.getByTestId('code-view').locator('summary').click()
    await expect(page.getByTestId('code-view').locator('pre').first()).toBeVisible()
  })
})

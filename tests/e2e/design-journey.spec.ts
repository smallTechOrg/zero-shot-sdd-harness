import { expect, test, type Page } from '@playwright/test'

const CANONICAL_PROMPT =
  'single box culvert, 4 m clear span, 3 m height, 2.5 m cushion, BG single line, 25t loading'

const step = (page: Page, name: string) => page.locator(`[data-testid="step-${name}"]`)

test.describe('primary design journey (real backend + Gemini)', () => {
  test('canonical prompt: styled render, live tracker, calc sheet, drawing, proof-check, stubs, cost badge', async ({
    page,
    request,
  }) => {
    test.setTimeout(300_000)

    // --- 1. Styled render ---------------------------------------------------
    const cssStatuses: number[] = []
    page.on('response', response => {
      if (response.url().includes('/_next/static/css/') || response.url().endsWith('.css')) {
        cssStatuses.push(response.status())
      }
    })

    await page.goto('/app/')
    await expect(page.getByRole('banner')).toContainText('IR Box Culvert Design & Proof-Check Agent')

    expect(cssStatuses.length, 'at least one stylesheet must be requested').toBeGreaterThan(0)
    expect(cssStatuses, 'stylesheet must load with 200').toContain(200)

    const headerBg = await page.evaluate(() => getComputedStyle(document.querySelector('header')!).backgroundColor)
    expect(headerBg, 'header must be styled, not browser-default transparent').not.toBe('rgba(0, 0, 0, 0)')
    expect(headerBg, 'header must be styled, not plain white').not.toBe('rgb(255, 255, 255)')

    // --- 2. Submit the canonical prompt; tracker advances in order ----------
    await page.getByTestId('prompt-input').fill(CANONICAL_PROMPT)
    await page.getByTestId('prompt-submit').click()
    // Feedback within ~100 ms: the disable is synchronous with the click handler.
    await expect(page.getByTestId('prompt-submit')).toBeDisabled({ timeout: 500 })

    await expect(step(page, 'Understand')).toHaveAttribute('data-status', /active|done/, { timeout: 60_000 })
    await expect(step(page, 'Extract')).toHaveAttribute('data-status', /active|done/, { timeout: 90_000 })
    await expect(step(page, 'Analyse')).toHaveAttribute('data-status', /active|done/, { timeout: 120_000 })

    // --- 3. Calc Sheet streams in BEFORE the review completes ---------------
    // The calc_sheet artefact fires at the end of Check; Review (FE re-solve +
    // memo) runs after. Seeing sheet content while Review is not yet done is
    // the DOM-level proxy for the artefact-before-review-done SSE ordering.
    await page.getByTestId('tab-calc-sheet').click()
    await expect(page.getByTestId('calc-assumptions')).toBeVisible({ timeout: 180_000 })
    expect(
      await step(page, 'Review').getAttribute('data-status'),
      'calc sheet must arrive before the Review step completes',
    ).not.toBe('done')

    // Assumptions block + all four sections.
    const sectionCount = await page.getByTestId('calc-section').count()
    expect(sectionCount, 'the sheet must contain the four sections').toBeGreaterThanOrEqual(4)

    // Every loading line carries its citation; the ACS correction-slip level
    // must be visible on the loading lines.
    const loadingSection = page.locator('[data-testid="calc-section"][data-section-id="loading"]')
    await expect(loadingSection).toBeVisible()
    await expect(
      loadingSection.locator('[data-testid="calc-citation"]').filter({ hasText: 'ACS' }).first(),
    ).toBeVisible()

    // Drill-down: expanding a trail row reveals the formula + substituted inputs.
    await page.getByTestId('calc-row-expand').first().click()
    const trail = page.getByTestId('calc-trail').first()
    await expect(trail).toBeVisible()
    const formulaText = (await trail.getByTestId('calc-trail-formula').first().textContent()) ?? ''
    expect(formulaText.trim().length, 'the trail must show a real formula').toBeGreaterThan(0)
    await expect(trail.getByTestId('calc-trail-inputs').first()).toBeVisible()
    const inputCount = await trail.locator('[data-testid="calc-trail-input"]').count()
    expect(inputCount, 'the trail must show substituted inputs').toBeGreaterThan(0)

    // --- 4. Check and Review are REAL steps now (done, never skipped) -------
    await expect(step(page, 'Check')).toHaveAttribute('data-status', 'done', { timeout: 180_000 })
    await expect(step(page, 'Review')).toHaveAttribute('data-status', 'done', { timeout: 180_000 })

    // Regression (F1): model3d publishes a Draw "skipped" tag AFTER draw marked
    // it done — the live tracker must keep Draw done, never downgrade it.
    await expect(step(page, 'Draw')).toHaveAttribute('data-status', 'done', { timeout: 180_000 })

    // --- 5. Real inline SVG drawing with pan/zoom-ready DOM -----------------
    await page.getByTestId('tab-drawing').click()
    const svg = page.locator('[data-testid="drawing-svg"] svg')
    await expect(svg).toBeVisible({ timeout: 180_000 })
    const svgChildCount = await page.locator('[data-testid="drawing-svg"] svg *').count()
    expect(svgChildCount, 'GA drawing SVG must contain real geometry').toBeGreaterThan(10)

    // Run must finish (button re-enables as Refine) before final artefact checks.
    await expect(page.getByTestId('prompt-submit')).toHaveText('Refine', { timeout: 180_000 })
    await expect(page.getByTestId('prompt-submit')).toBeEnabled()

    // --- 6. Proof-Check tab: verdict banner, 12-row matrix, BMD/SFD ---------
    await page.getByTestId('tab-proof-check').click()
    const banner = page.getByTestId('verdict-banner')
    await expect(banner).toBeVisible({ timeout: 30_000 })
    await expect(banner).toHaveAttribute('data-verdict', 'recommended_for_approval')
    await expect(banner).toContainText('Recommended for approval')

    await expect(page.getByTestId('memo')).toBeVisible({ timeout: 30_000 })
    await expect(page.getByTestId('compliance-row')).toHaveCount(12, { timeout: 30_000 })

    await expect(page.locator('[data-testid="bmd-svg"] svg')).toBeVisible({ timeout: 30_000 })
    await expect(page.locator('[data-testid="sfd-svg"] svg')).toBeVisible({ timeout: 30_000 })
    await expect(page.getByTestId('fe-agreement')).toContainText(/agrees within [\d.]+%/)

    // --- 7. Genuine DXF download ---------------------------------------------
    const runId = await page.getByTestId('step-tracker').getAttribute('data-run-id')
    expect(runId, 'tracker must expose the run id').toBeTruthy()

    const dxfResponse = await request.get(`/api/designs/${runId}/artifacts/ga.dxf`)
    expect(dxfResponse.status()).toBe(200)
    expect(dxfResponse.headers()['content-disposition'] ?? '').toContain('attachment')
    const dxfBody = await dxfResponse.body()
    expect(dxfBody.length, 'DXF must be a non-trivial file').toBeGreaterThan(5 * 1024)

    // --- 8. Remaining stubs are unmistakable roadmap panels, not bugs -------
    await page.getByTestId('tab-3d-model').click()
    await expect(page.getByTestId('stub-3d-model')).toContainText('Coming in Phase 3 — nothing to try here yet')
    await page.getByTestId('tab-library').click()
    await expect(page.getByTestId('stub-library')).toContainText('Coming in Phase 3 — nothing to try here yet')
    await expect(page.getByTestId('suggestion-stub-chip')).toContainText('coming in Phase 3')

    // --- 9. Token/cost badge shows a real, non-zero token count -------------
    const badgeText = (await page.getByTestId('token-cost-badge').textContent()) ?? ''
    expect(badgeText).toMatch(/tok · \$[\d.]+ run · \$[\d.]+ session/)
    const tokenMatch = badgeText.match(/^([\d.]+)(k?) tok/)
    expect(tokenMatch, `badge must lead with a token count, got: ${badgeText}`).toBeTruthy()
    const tokenCount = parseFloat(tokenMatch![1]) * (tokenMatch![2] === 'k' ? 1000 : 1)
    expect(tokenCount, 'a real Gemini run must report non-zero tokens').toBeGreaterThan(0)
  })
})

import { expect, test, type Page } from '@playwright/test'

const CANONICAL_PROMPT =
  'single box culvert, 4 m clear span, 3 m height, 2.5 m cushion, BG single line, 25t loading'

const step = (page: Page, name: string) => page.locator(`[data-testid="step-${name}"]`)

test.describe('primary design journey (real backend + Gemini)', () => {
  test('canonical prompt: styled render, live tracker, real GA drawing, DXF, stubs, cost badge', async ({
    page,
    request,
  }) => {
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
    await expect(step(page, 'Draw')).toHaveAttribute('data-status', /active|done/, { timeout: 180_000 })

    // Skipped steps are labelled roadmap items, never failures.
    await expect(step(page, 'Check')).toHaveAttribute('data-status', 'skipped', { timeout: 180_000 })
    await expect(step(page, 'Check')).toContainText('Coming in Phase')
    await expect(step(page, 'Review')).toHaveAttribute('data-status', 'skipped', { timeout: 180_000 })
    await expect(step(page, 'Review')).toContainText('Coming in Phase')

    // Regression (F1): model3d publishes a Draw "skipped" tag AFTER draw marked
    // it done — the live tracker must keep Draw done, never downgrade it.
    await expect(step(page, 'Draw')).toHaveAttribute('data-status', 'done', { timeout: 180_000 })

    // --- 3. Real inline SVG drawing with pan/zoom-ready DOM -----------------
    await page.getByTestId('tab-drawing').click()
    const svg = page.locator('[data-testid="drawing-svg"] svg')
    await expect(svg).toBeVisible({ timeout: 180_000 })
    const svgChildCount = await page.locator('[data-testid="drawing-svg"] svg *').count()
    expect(svgChildCount, 'GA drawing SVG must contain real geometry').toBeGreaterThan(10)

    // Run must finish (button re-enables as Refine) before artefact checks.
    await expect(page.getByTestId('prompt-submit')).toHaveText('Refine', { timeout: 180_000 })
    await expect(page.getByTestId('prompt-submit')).toBeEnabled()

    // --- 4. Genuine DXF download ---------------------------------------------
    const runId = await page.getByTestId('step-tracker').getAttribute('data-run-id')
    expect(runId, 'tracker must expose the run id').toBeTruthy()

    const dxfResponse = await request.get(`/api/designs/${runId}/artifacts/ga.dxf`)
    expect(dxfResponse.status()).toBe(200)
    expect(dxfResponse.headers()['content-disposition'] ?? '').toContain('attachment')
    const dxfBody = await dxfResponse.body()
    expect(dxfBody.length, 'DXF must be a non-trivial file').toBeGreaterThan(5 * 1024)

    // --- 5. Stub tabs are labelled roadmap panels, not bugs ------------------
    await page.getByTestId('tab-calc-sheet').click()
    await expect(page.getByTestId('stub-calc-sheet')).toContainText('Coming in Phase 2')
    await page.getByTestId('tab-proof-check').click()
    await expect(page.getByTestId('stub-proof-check')).toContainText('Coming in Phase 2')
    await page.getByTestId('tab-3d-model').click()
    await expect(page.getByTestId('stub-3d-model')).toContainText('Coming in Phase 3')
    await page.getByTestId('tab-library').click()
    await expect(page.getByTestId('stub-library')).toContainText('Coming in Phase 3')

    // --- 6. Token/cost badge shows a real, non-zero token count -------------
    const badgeText = (await page.getByTestId('token-cost-badge').textContent()) ?? ''
    expect(badgeText).toMatch(/tok · \$[\d.]+ run · \$[\d.]+ session/)
    const tokenMatch = badgeText.match(/^([\d.]+)(k?) tok/)
    expect(tokenMatch, `badge must lead with a token count, got: ${badgeText}`).toBeTruthy()
    const tokenCount = parseFloat(tokenMatch![1]) * (tokenMatch![2] === 'k' ? 1000 : 1)
    expect(tokenCount, 'a real Gemini run must report non-zero tokens').toBeGreaterThan(0)
  })
})

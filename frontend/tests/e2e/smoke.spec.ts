import { test, expect } from '@playwright/test'

// Phase 1 smoke: the workspace shell renders, is styled, the primary upload
// interaction is present, and the labelled NON-FUNCTIONAL stubs are visible
// so a tester never mistakes them for bugs.
// Runs against the live single-origin server at http://localhost:8001/app/.

test.describe('Workspace shell (Phase 1)', () => {
  test('loads, is styled, and shows the upload zone', async ({ page }) => {
    await page.goto('')

    // Title + header render.
    await expect(page).toHaveTitle(/Data Analysis Agent/i)
    await expect(
      page.getByRole('heading', { name: 'Data Analysis Agent' }),
    ).toBeVisible()

    // Primary interaction: the upload dropzone is present and labelled.
    const upload = page.getByTestId('upload-zone')
    await expect(upload).toBeVisible()
    await expect(upload.getByText(/Drop a CSV or Excel file here/i)).toBeVisible()

    // Tailwind actually compiled — the dropzone has a real, non-default background.
    const bg = await upload
      .locator('[role="button"]')
      .first()
      .evaluate(el => getComputedStyle(el).backgroundColor)
    expect(bg).not.toBe('')
    expect(bg).not.toBe('rgba(0, 0, 0, 0)')
  })

  test('shows the cost meter', async ({ page }) => {
    await page.goto('')
    await expect(page.getByTestId('cost-meter')).toBeVisible()
  })

  test('labelled Phase 2/3 stubs are visible and tagged (not bugs)', async ({ page }) => {
    await page.goto('')

    // Dataset Library sidebar stub — tagged "Coming in Phase 2".
    const sidebar = page.getByTestId('library-sidebar')
    await expect(sidebar).toBeVisible()
    await expect(page.getByTestId('phase2-badge')).toHaveText(/Coming in Phase 2/i)
  })
})

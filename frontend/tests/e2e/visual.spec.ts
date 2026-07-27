import { b02DeviceId, b02From, b02To, expect, gotoScenario, test } from './helpers'

const routes = [
  { route: '/', scenario: 'active-anomaly', snapshot: 'overview.png' },
  {
    route: `/sensors/${b02DeviceId}?sensor=${b02DeviceId}&from=${b02From}&to=${b02To}&bucket=raw`,
    scenario: 'data-gap',
    snapshot: 'sensors-b02.png',
  },
  { route: '/alerts', scenario: 'active-anomaly', snapshot: 'alerts.png' },
  { route: '/model-evaluation', scenario: 'active-anomaly', snapshot: 'model-evaluation.png' },
  { route: '/system-health', scenario: 'stale', snapshot: 'system-health.png' },
] as const

const canonicalEdaRoute = '/eda?mode=precompute&period_kind=monthly&run=run-b02-canonical-v3'
const edaViewports = [
  { width: 390, height: 844, snapshot: 'eda-390.png' },
  { width: 1280, height: 900, snapshot: 'eda-1280.png' },
  { width: 1440, height: 900, snapshot: 'eda.png' },
  { width: 1920, height: 1080, snapshot: 'eda-1920.png' },
] as const

for (const { route, scenario, snapshot } of routes) {
  test(`${route} ${scenario} visual`, async ({ page }) => {
    await gotoScenario(page, route, scenario)
    await page.waitForLoadState('networkidle')
    await page.evaluate(() => document.fonts.ready)
    await expect(page).toHaveScreenshot(snapshot, {
      animations: 'disabled',
      caret: 'hide',
      fullPage: true,
    })
  })
}

for (const { width, height, snapshot } of edaViewports) {
  test(`canonical EDA ${width}px visual`, async ({ page }) => {
    await page.setViewportSize({ width, height })
    await gotoScenario(page, canonicalEdaRoute, 'eda-canonical')
    await expect(page.getByRole('button', { name: 'Lihat data bootstrap' })).toBeVisible()
    await page.evaluate(() => document.fonts.ready)
    await expect(page).toHaveScreenshot(snapshot, {
      animations: 'disabled',
      caret: 'hide',
      fullPage: true,
      timeout: 15_000,
    })
  })
}

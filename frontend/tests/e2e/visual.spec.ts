import { expect, gotoScenario, test } from './helpers'

const routes = [
  { route: '/', snapshot: 'overview.png' },
  { route: '/sensors/n4', snapshot: 'sensors-n4.png' },
  { route: '/alerts', snapshot: 'alerts.png' },
  { route: '/eda', snapshot: 'eda.png' },
  { route: '/model-evaluation', snapshot: 'model-evaluation.png' },
  { route: '/system-health', snapshot: 'system-health.png' },
] as const

for (const { route, snapshot } of routes) {
  test(`${route} active anomaly visual`, async ({ page }) => {
    await gotoScenario(page, route, 'active-anomaly')
    await page.waitForLoadState('networkidle')
    await page.evaluate(() => document.fonts.ready)

    await expect(page).toHaveScreenshot(snapshot, {
      animations: 'disabled',
      caret: 'hide',
      fullPage: true,
    })
  })
}

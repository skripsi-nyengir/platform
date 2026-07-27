import {
  disableAppQueryRetries,
  expect,
  expectVisibleFocus,
  gotoScenario,
  resetAppQuery,
  setMockScenarioOnPage,
  tabTo,
  test,
} from './helpers'

const canonicalRoute = '/eda?mode=precompute&period_kind=monthly&run=run-b02-canonical-v3'

test('keyboard reaches the responsive alert action', async ({ page }) => {
  await gotoScenario(page, '/alerts', 'active-anomaly')
  const action = page.getByRole('button', { name: 'Acknowledge alert' })
  await tabTo(page, action)
  await expectVisibleFocus(action)
})

test('overview charts expose no tabbable proxies', async ({ page }) => {
  await gotoScenario(page, '/', 'active-anomaly')
  const charts = page.getByRole('img', { name: /Recent (Temperature|RH) history/ })
  await expect(charts).toHaveCount(2)
  await expect(charts.locator('[tabindex="0"]')).toHaveCount(0)
})

test('keyboard reaches every precompute control and the EDA anchor index', async ({ page }) => {
  await gotoScenario(page, canonicalRoute, 'eda-canonical')
  await expect(page.getByRole('button', { name: 'Lihat data bootstrap' })).toBeVisible()

  const mode = page.getByRole('combobox', { name: 'Mode' })
  const periodKind = page.getByRole('combobox', { name: 'Jenis periode' })
  const period = page.getByRole('combobox', { name: 'Periode tersedia' })
  const qualityAnchor = page.getByRole('navigation', { name: 'Indeks bagian EDA' })
    .getByRole('link', { name: 'Kualitas Data' })

  for (const control of [mode, periodKind, period, qualityAnchor]) {
    await tabTo(page, control)
    await expectVisibleFocus(control)
  }
})

test('keyboard activates a scoped section retry', async ({ page, httpErrorGuard }) => {
  httpErrorGuard.allow(503)
  await gotoScenario(page, canonicalRoute, 'eda-canonical')
  await expect(page.getByRole('button', { name: 'Lihat data bootstrap' })).toBeVisible()
  await disableAppQueryRetries(page)
  await setMockScenarioOnPage(page, 'eda-section-error')
  await resetAppQuery(page, [
    'eda',
    'run',
    'run-b02-canonical-v3',
    'section',
    'uncertainty',
  ])
  const panel = page.getByRole('heading', { name: 'Ketidakpastian bootstrap asosiasi' })
    .locator('xpath=ancestor::section[1]')
  const retry = panel.getByRole('button', { name: 'Retry' })

  await tabTo(page, retry, 160)
  await expectVisibleFocus(retry)
  await page.keyboard.press('Enter')

  await expect(panel.getByRole('alert')).toHaveCount(0)
})

test('bounded data dialog contains keyboard focus and returns it to the trigger', async ({ page }) => {
  await gotoScenario(page, canonicalRoute, 'eda-canonical')
  const trigger = page.getByRole('button', { name: 'Lihat data bootstrap' })
  await expect(trigger).toBeVisible()

  await tabTo(page, trigger, 160)
  await expectVisibleFocus(trigger)
  await page.keyboard.press('Enter')

  const dialog = page.getByRole('dialog', { name: 'Data bootstrap asosiasi median harian' })
  await expect(dialog).toBeVisible()
  expect(await dialog.evaluate((element) => element.contains(document.activeElement))).toBe(true)
  await page.keyboard.press('Tab')
  expect(await dialog.evaluate((element) => element.contains(document.activeElement))).toBe(true)
  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
  await expect(trigger).toBeFocused()
})

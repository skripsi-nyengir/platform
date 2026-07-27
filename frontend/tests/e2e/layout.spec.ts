import { b02DeviceId, b02From, b02To, expect, gotoScenario, test } from './helpers'

const canonicalEdaRoute = '/eda?mode=precompute&period_kind=monthly&run=run-b02-canonical-v3'
const edaPanelHeadings = [
  'Audit pairing timestamp',
  'Kepadatan gabungan Suhu–RH',
  'Diagnostik univariat',
  'Excerpt kejadian kualitas',
  'Integritas kualitas',
  'Cakupan kalender temporal',
  'Cakupan hari × jam',
  'Distribusi temporal Suhu dan RH',
  'Ringkasan asosiasi Suhu–RH',
  'Korelasi Pearson bergulir',
  'Ketidakpastian bootstrap asosiasi',
  'Kelayakan struktur temporal',
  'Autokorelasi ACF dan PACF',
  'Spektrum frekuensi',
  'Dekomposisi STL',
  'Kandidat perubahan rezim',
] as const

async function expectNoHorizontalOverflow(page: Parameters<typeof gotoScenario>[0]): Promise<void> {
  const dimensions = await page.evaluate(() => ({
    client: document.documentElement.clientWidth,
    scroll: document.documentElement.scrollWidth,
  }))
  expect(dimensions.scroll).toBe(dimensions.client)
}

const routes = [
  '/',
  `/sensors/${b02DeviceId}?sensor=${b02DeviceId}&from=${b02From}&to=${b02To}&bucket=raw`,
  '/alerts',
  '/eda',
  '/model-evaluation',
  '/system-health',
] as const

for (const route of routes) {
  test(`${route} has no horizontal page overflow`, async ({ page }) => {
    await gotoScenario(page, route, 'active-anomaly')
    await page.waitForLoadState('networkidle')
    await expectNoHorizontalOverflow(page)
  })
}

test('dense canonical EDA has no horizontal overflow at 1280 and 1920', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === 'desktop-1440')
  await gotoScenario(page, canonicalEdaRoute, 'eda-canonical')
  await expect(page.getByRole('button', { name: 'Lihat data bootstrap' })).toBeVisible()

  await expectNoHorizontalOverflow(page)
  for (const heading of edaPanelHeadings) {
    await expect(page.getByRole('heading', { name: heading })).toBeVisible()
  }
})

test('dense canonical EDA stays legible and contained at 390px', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-1280')
  await page.setViewportSize({ width: 390, height: 844 })
  await gotoScenario(page, canonicalEdaRoute, 'eda-canonical')
  await expect(page.getByRole('button', { name: 'Lihat data bootstrap' })).toBeVisible()

  await expectNoHorizontalOverflow(page)
  await expect(page.getByRole('navigation', { name: 'Indeks bagian EDA' })).toBeVisible()
  for (const heading of edaPanelHeadings) {
    const panelHeading = page.getByRole('heading', { name: heading })
    await panelHeading.scrollIntoViewIfNeeded()
    await expect(panelHeading).toBeVisible()
    const box = await panelHeading.locator('xpath=ancestor::section[1]').boundingBox()
    expect(box).not.toBeNull()
    if (box !== null) {
      expect(box.x).toBeGreaterThanOrEqual(0)
      expect(box.x + box.width).toBeLessThanOrEqual(390)
    }
  }
})

test('alert action remains reachable at responsive width', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-1280')
  await page.setViewportSize({ width: 390, height: 844 })
  await gotoScenario(page, '/alerts', 'active-anomaly')
  const action = page.getByRole('button', { name: 'Acknowledge alert' })
  await action.scrollIntoViewIfNeeded()
  await expect(action).toBeVisible()
  const box = await action.boundingBox()
  expect(box).not.toBeNull()
  if (box !== null) {
    expect(box.x).toBeGreaterThanOrEqual(0)
    expect(box.x + box.width).toBeLessThanOrEqual(390)
  }
})

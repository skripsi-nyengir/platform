import {
  b02DeviceId,
  b02From,
  b02To,
  expect,
  expectVisibleFocus,
  gotoScenario,
  seedThemeMode,
  tabTo,
  test,
} from './helpers'

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
  '/simulation',
  '/system-health',
] as const

for (const route of routes) {
  test(`${route} has no horizontal page overflow`, async ({ page }) => {
    await gotoScenario(page, route, 'active-anomaly')
    await page.waitForLoadState('networkidle')
    await expectNoHorizontalOverflow(page)
  })
}

test('model evaluation cards, selector, chart, and dialog stay contained at 390px', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-1280')
  await page.setViewportSize({ width: 390, height: 844 })
  await gotoScenario(page, '/model-evaluation', 'active-anomaly')

  const registry = page.getByRole('region', {
    name: 'Model terdaftar (metrik dilaporkan dari training)',
  })
  await expect(registry.getByRole('article')).toHaveCount(5)
  await expectNoHorizontalOverflow(page)

  const registryBoxes = await Promise.all(
    (await registry.getByRole('article').all()).map((card) => card.boundingBox()),
  )
  for (const box of registryBoxes) {
    expect(box).not.toBeNull()
    if (box !== null) {
      expect(box.x).toBeGreaterThanOrEqual(0)
      expect(box.x + box.width).toBeLessThanOrEqual(390)
    }
  }
  expect(new Set(registryBoxes.map((box) => Math.round(box?.x ?? -1))).size).toBe(1)

  await registry.getByRole('button', { name: 'Detail teknis' }).first().click()
  const registryDialog = page.getByRole('dialog', {
    name: 'Detail teknis registry · Conv1D Autoencoder',
  })
  await expect(registryDialog).toContainText('b02f3872_ruang_produksi_v3_march07')
  await expectNoHorizontalOverflow(page)
  await registryDialog.getByRole('button', { name: 'Tutup' }).click()

  const selectorButtons = page.getByRole('button', {
    name: /^(Conv1D|GRU|LSTM|RNN|Transformer)$/,
  })
  await expect(selectorButtons).toHaveCount(5)
  const selectorBoxes = await Promise.all(
    (await selectorButtons.all()).map((button) => button.boundingBox()),
  )
  expect(selectorBoxes.every((box) => box !== null && box.height >= 44)).toBe(true)
  expect(new Set(selectorBoxes.map((box) => box?.y)).size).toBeGreaterThan(1)

  const chart = page.getByRole('img', {
    name: 'Perbandingan precision recall dan F1 lima model pada bin evaluasi',
  })
  await chart.scrollIntoViewIfNeeded()
  const chartBox = await chart.boundingBox()
  expect(chartBox).not.toBeNull()
  if (chartBox !== null) expect(chartBox.x + chartBox.width).toBeLessThanOrEqual(390)

  await page.getByRole('button', { name: 'Lihat data eksak' }).click()
  await expect(page.getByRole('dialog', { name: 'Data eksak evaluasi Step 7' })).toBeVisible()
  await expectNoHorizontalOverflow(page)
})

test('system health evidence and service cards stay contained at 390px', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-1280')
  await page.setViewportSize({ width: 390, height: 844 })
  await gotoScenario(page, '/system-health', 'stale')

  const dashboard = page.getByRole('region', { name: 'System health current snapshot' })
  const telemetryHealth = dashboard.getByRole('region', { name: 'Live telemetry health' })
  await expect(telemetryHealth.getByRole('heading', { name: 'Live telemetry health' })).toBeVisible()
  await expect(telemetryHealth.getByText('Degraded', { exact: true })).toBeVisible()
  await expect(dashboard.getByText('10m 1s')).toBeVisible()
  await expect(dashboard.getByText('Ready 5')).toBeVisible()
  await expect(dashboard.getByText('Not ready 2')).toBeVisible()
  const evidence = dashboard.getByRole('region', { name: 'Snapshot evidence' })
  await expect(evidence).toContainText('Latest telemetry (Asia/Jakarta, WIB)')
  const services = dashboard.getByRole('region', { name: 'Service status' })
  await expect(services.getByRole('article')).toHaveCount(7)
  await expectNoHorizontalOverflow(page)

  const cardBoxes = await Promise.all(
    (await services.getByRole('article').all()).map((card) => card.boundingBox()),
  )
  expect(cardBoxes.every((box) => box !== null && box.x + box.width <= 390)).toBe(true)
  expect(new Set(cardBoxes.map((box) => Math.round(box?.x ?? -1))).size).toBe(1)

  const technicalDetails = dashboard.getByRole('button', { name: /Technical details/ })
  await technicalDetails.click()
  await expect(dashboard.getByText('Request ID: req_system_status')).toBeVisible()
  await expectNoHorizontalOverflow(page)
})

for (const { label, route } of [
  { label: 'overview', route: '/' },
  {
    label: 'sensor detail',
    route: `/sensors/${b02DeviceId}?sensor=${b02DeviceId}&from=${b02From}&to=${b02To}&bucket=raw`,
  },
] as const) {
  test(`${label} compact telemetry health stays concise and contained at 390px`, async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'desktop-1280')
    await page.setViewportSize({ width: 390, height: 844 })
    await gotoScenario(page, route, 'active-anomaly')

    const telemetryHealth = page.getByRole('region', { name: 'Live telemetry health' })
    await expect(telemetryHealth.getByRole('heading', { name: 'Live telemetry health' })).toBeVisible()
    await expect(telemetryHealth.getByRole('group', { name: 'Live telemetry indicators' }).getByRole('article')).toHaveCount(4)
    await expect(telemetryHealth.getByRole('button', { name: /Technical details/ })).toHaveCount(0)
    await expectNoHorizontalOverflow(page)

    const box = await telemetryHealth.boundingBox()
    expect(box).not.toBeNull()
    if (box !== null) {
      expect(box.x).toBeGreaterThanOrEqual(0)
      expect(box.x + box.width).toBeLessThanOrEqual(390)
    }
  })
}

test('system health service grid uses three desktop and two tablet columns', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-1280')
  await gotoScenario(page, '/system-health', 'normal')

  const cards = page
    .getByRole('region', { name: 'Service status' })
    .getByRole('article')
  await expect(cards).toHaveCount(7)
  const desktopBoxes = await Promise.all(
    (await cards.all()).slice(0, 4).map((card) => card.boundingBox()),
  )
  expect(desktopBoxes.slice(0, 3).map((box) => Math.round(box?.y ?? -1))).toEqual([
    Math.round(desktopBoxes[0]?.y ?? -1),
    Math.round(desktopBoxes[0]?.y ?? -1),
    Math.round(desktopBoxes[0]?.y ?? -1),
  ])
  expect(Math.round(desktopBoxes[3]?.y ?? -1)).toBeGreaterThan(
    Math.round(desktopBoxes[0]?.y ?? -1),
  )

  await page.setViewportSize({ width: 900, height: 900 })
  const tabletBoxes = await Promise.all(
    (await cards.all()).slice(0, 3).map((card) => card.boundingBox()),
  )
  expect(Math.round(tabletBoxes[1]?.y ?? -1)).toBe(Math.round(tabletBoxes[0]?.y ?? -1))
  expect(Math.round(tabletBoxes[2]?.y ?? -1)).toBeGreaterThan(
    Math.round(tabletBoxes[0]?.y ?? -1),
  )
  await expectNoHorizontalOverflow(page)
})

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

test('compact theme toggle remains visible, labelled, focusable, and contained', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-1280')
  await page.setViewportSize({ width: 390, height: 844 })
  await seedThemeMode(page, 'dark')
  await gotoScenario(page, '/', 'active-anomaly')

  const toggle = page.getByRole('button', { name: 'Switch to light theme' })
  await expect(toggle).toBeVisible()
  await expect(toggle).toBeEnabled()
  await expect(page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('button')).toHaveCount(0)
  await expect(page.locator('footer').getByRole('button', { name: 'Switch to light theme' })).toBeVisible()
  const box = await toggle.boundingBox()
  expect(box).not.toBeNull()
  if (box !== null) {
    expect(box.width).toBeGreaterThanOrEqual(44)
    expect(box.height).toBeGreaterThanOrEqual(44)
    expect(box.x).toBeGreaterThanOrEqual(0)
    expect(box.x + box.width).toBeLessThanOrEqual(72)
  }

  await toggle.hover()
  await expect(page.getByRole('tooltip', { name: 'Switch to light theme' })).toBeVisible()
  await tabTo(page, toggle)
  await expectVisibleFocus(toggle)
  await page.keyboard.press('Enter')
  await expect(page.getByRole('button', { name: 'Switch to dark theme' })).toBeFocused()
  await expectNoHorizontalOverflow(page)
})

test('desktop sidebar collapses to the compact rail and persists across reloads', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-1280')
  await gotoScenario(page, '/', 'active-anomaly')
  await page.evaluate(() => window.localStorage.removeItem('adp-sidebar-collapsed'))
  await page.reload()

  const collapse = page.getByRole('button', { name: 'Collapse sidebar' })
  await expect(collapse).toHaveAttribute('aria-expanded', 'true')
  await collapse.click()

  const expand = page.getByRole('button', { name: 'Expand sidebar' })
  await expect(expand).toHaveAttribute('aria-expanded', 'false')
  await expect(page.getByRole('link', { name: 'Overview' })).toBeVisible()
  const navigation = page.getByRole('navigation', { name: 'Primary navigation' })
  await expect.poll(async () => (await navigation.boundingBox())?.width ?? Number.POSITIVE_INFINITY)
    .toBeLessThanOrEqual(72)
  await expectNoHorizontalOverflow(page)

  await page.reload()
  await expect(page.getByRole('button', { name: 'Expand sidebar' })).toBeVisible()
  await expectNoHorizontalOverflow(page)
})

import type { Locator } from '@playwright/test'
import { expect, expectVisibleFocus, gotoScenario, test } from './helpers'

const routes = [
  { name: 'Overview', route: '/' },
  {
    name: 'Sensor Detail & History',
    route: '/sensors/n4?sensor=n4&from=2026-07-19T10%3A00%3A00Z&to=2026-07-19T10%3A30%3A00Z&bucket=5m',
  },
  { name: 'Alerts', route: '/alerts' },
  { name: 'EDA', route: '/eda' },
  { name: 'Model Evaluation', route: '/model-evaluation' },
  { name: 'System Health', route: '/system-health' },
] as const

const controlSelector = [
  'a[href]',
  'button',
  'input',
  'select',
  'textarea',
  '[role="button"]',
  '[role="checkbox"]',
  '[role="combobox"]',
  '[role="link"]',
  '[role="radio"]',
  '[role="tab"]',
  '[role="gridcell"][tabindex="0"]',
  '[role="columnheader"][tabindex="0"]',
].join(',')

const visibleTextSelector = [
  'h1', 'h2', 'h3', 'h4', 'p', 'li', 'dt', 'dd', 'th', 'td',
  '[role="heading"]', '[role="status"]', '[role="alert"]', '[role="img"]',
].join(',')

const layoutTolerance = 0.5

async function expectWithinBounds(elements: Locator, container: Locator) {
  await expect(container).toBeVisible()
  const [containerBox, elementBoxes] = await Promise.all([
    container.boundingBox(),
    elements.evaluateAll((nodes) => nodes.flatMap((node) => {
      const rect = node.getBoundingClientRect()
      const style = getComputedStyle(node)
      return style.display === 'none' || style.visibility === 'hidden' || rect.width === 0 || rect.height === 0
        ? []
        : [rect.toJSON()]
    })),
  ])

  expect(containerBox).not.toBeNull()
  expect(elementBoxes.length).toBeGreaterThan(0)
  if (containerBox === null) return

  for (const box of elementBoxes) {
    expect(box.left).toBeGreaterThanOrEqual(containerBox.x - layoutTolerance)
    expect(box.right).toBeLessThanOrEqual(containerBox.x + containerBox.width + layoutTolerance)
    expect(box.top).toBeGreaterThanOrEqual(containerBox.y - layoutTolerance)
    expect(box.bottom).toBeLessThanOrEqual(containerBox.y + containerBox.height + layoutTolerance)
  }
}

async function gridColumnCount(grid: Locator) {
  return grid.evaluate(
    (element, tolerance) => getComputedStyle(element).gridTemplateColumns
      .split(/\s+/)
      .filter(Boolean)
      .filter((track) => Number.parseFloat(track) > tolerance)
      .length,
    layoutTolerance,
  )
}

test('Overview uses a compact permanent navigation rail at 390px', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-1280')
  await page.setViewportSize({ width: 390, height: 844 })
  await gotoScenario(page, '/', 'active-anomaly')
  await page.evaluate(async () => {
    await document.fonts.ready
  })

  const drawerRoot = page.locator('.MuiDrawer-root')
  const drawerPaper = page.locator('.MuiDrawer-paper')
  const main = page.locator('main')
  const [drawerRootBox, drawerPaperBox, mainBox] = await Promise.all([
    drawerRoot.boundingBox(),
    drawerPaper.boundingBox(),
    main.boundingBox(),
  ])
  expect(drawerRootBox).not.toBeNull()
  expect(drawerPaperBox).not.toBeNull()
  expect(mainBox).not.toBeNull()
  if (drawerRootBox === null || drawerPaperBox === null || mainBox === null) return

  expect(Math.abs(drawerPaperBox.width - 72)).toBeLessThanOrEqual(layoutTolerance)
  expect(Math.abs(mainBox.x - 72)).toBeLessThanOrEqual(layoutTolerance)
  expect(Math.abs(mainBox.width - 318)).toBeLessThanOrEqual(layoutTolerance)
  expect(drawerRootBox.height).toBeGreaterThanOrEqual(844)
  await expect(drawerRoot).toHaveCSS('border-right-width', '1px')
  await expect(drawerRoot).toHaveCSS('border-right-style', 'solid')
  await expect(drawerPaper).toHaveCSS('border-right-width', '0px')

  await expect(page.getByText('ADP', { exact: true })).toBeVisible()
  await expect(page.getByText('Anomaly Detection Platform', { exact: true })).toBeHidden()
  await expect(page.getByText('IoT sensor operations', { exact: true })).toBeHidden()

  const navigation = page.getByRole('navigation', { name: 'Primary navigation' })
  const navigationLinks = navigation.getByRole('link')
  await expect(navigationLinks).toHaveCount(6)
  const linkMetrics = await navigationLinks.evaluateAll((links) => links.map((link) => {
    const linkBox = link.getBoundingClientRect()
    const iconBox = link.querySelector('.MuiListItemIcon-root')?.getBoundingClientRect()
    const text = link.querySelector('.MuiListItemText-root')
    return {
      ariaLabel: link.getAttribute('aria-label'),
      height: linkBox.height,
      iconCenter: iconBox === undefined ? null : iconBox.left + iconBox.width / 2,
      linkCenter: linkBox.left + linkBox.width / 2,
      textDisplay: text === null ? null : getComputedStyle(text).display,
    }
  }))
  expect(linkMetrics.map(({ ariaLabel }) => ariaLabel)).toEqual([
    'Overview',
    'Sensors',
    'Alerts',
    'EDA',
    'Model Evaluation',
    'System Health',
  ])
  for (const metrics of linkMetrics) {
    expect(metrics.height).toBeGreaterThanOrEqual(44)
    expect(metrics.iconCenter).not.toBeNull()
    if (metrics.iconCenter !== null) {
      expect(Math.abs(metrics.iconCenter - metrics.linkCenter)).toBeLessThanOrEqual(layoutTolerance)
    }
    expect(metrics.textDisplay).toBe('none')
  }

  const activeLink = navigationLinks.first()
  await expect(activeLink).toHaveAttribute('aria-current', 'page')
  await expect(activeLink).toHaveCSS('border-left-width', '3px')
  await page.keyboard.press('Tab')
  await expectVisibleFocus(activeLink)

  const currentAlertActionLinks = page
    .getByRole('region', { name: 'Current alert for n4' })
    .getByRole('link')
  const sensorAlertActionLinks = page
    .getByRole('article', { name: 'Sensor n4' })
    .getByRole('link')
  await expect(currentAlertActionLinks).toHaveCount(2)
  await expect(sensorAlertActionLinks).toHaveCount(2)
  for (const links of [currentAlertActionLinks, sensorAlertActionLinks]) {
    const heights = await links.evaluateAll((nodes) =>
      nodes.map((node) => node.getBoundingClientRect().height),
    )
    for (const height of heights) expect(height).toBeGreaterThanOrEqual(44)
  }

  const summary = page.getByRole('region', { name: 'Operational summary' })
  const summaryCards = summary.locator('.MuiCard-root')
  await expect(summaryCards).toHaveCount(4)
  const [firstSummaryCardBox, secondSummaryCardBox, sensorCardBox] = await Promise.all([
    summaryCards.nth(0).boundingBox(),
    summaryCards.nth(1).boundingBox(),
    page.getByRole('article', { name: 'Sensor n1' }).boundingBox(),
  ])
  expect(firstSummaryCardBox).not.toBeNull()
  expect(secondSummaryCardBox).not.toBeNull()
  expect(sensorCardBox).not.toBeNull()
  if (firstSummaryCardBox !== null && secondSummaryCardBox !== null) {
    expect(Math.abs(firstSummaryCardBox.x - secondSummaryCardBox.x)).toBeLessThanOrEqual(layoutTolerance)
    expect(secondSummaryCardBox.y).toBeGreaterThan(firstSummaryCardBox.y + firstSummaryCardBox.height)
    expect(firstSummaryCardBox.width).toBeGreaterThanOrEqual(280)
  }
  if (sensorCardBox !== null) expect(sensorCardBox.width).toBeGreaterThanOrEqual(280)

  const viewportMetrics = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }))
  expect(viewportMetrics.scrollWidth).toBe(viewportMetrics.clientWidth)
})

for (const { name, route } of routes.filter(({ name }) => [
  'Overview',
  'Sensor Detail & History',
  'EDA',
  'Model Evaluation',
].includes(name))) {
  test(`${name} keeps mobile chart layouts within the body at 390px`, async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'desktop-1280')
    await page.setViewportSize({ width: 390, height: 844 })
    await gotoScenario(page, route, 'active-anomaly')
    await page.waitForLoadState('networkidle')
    await page.evaluate(async () => {
      await document.fonts.ready
    })

    const charts = page.locator('[role="img"]')
    await charts.first().waitFor({ state: 'visible', timeout: 2_000 })

    const viewportMetrics = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }))
    expect(viewportMetrics.scrollWidth).toBe(viewportMetrics.clientWidth)

    const body = page.locator('body')
    await expectWithinBounds(page.locator(controlSelector), body)
    await expectWithinBounds(page.locator(`:is(${visibleTextSelector}):not(th):not(td)`), body)
    await expectWithinBounds(charts, body)
  })
}

for (const { name, route } of routes) {
  test(`${name} has no horizontal overflow or clipped controls`, async ({ page }, testInfo) => {
    await gotoScenario(page, route, 'active-anomaly')
    await page.waitForLoadState('networkidle')
    await page.evaluate(async () => {
      await document.fonts.ready
    })
    await page.locator('[role="img"]').first().waitFor({ state: 'visible', timeout: 2_000 }).catch(() => undefined)

    if (testInfo.project.name === 'desktop-1280') {
      await page.evaluate(() => {
        document.body.style.minHeight = 'calc(100vh + 1px)'
      })
    }

    const metrics = await page.evaluate(() => ({
      client: document.documentElement.clientWidth,
      scroll: document.documentElement.scrollWidth,
      clientHeight: document.documentElement.clientHeight,
      scrollHeight: document.documentElement.scrollHeight,
    }))

    if (testInfo.project.name === 'desktop-1280') {
      expect(metrics.scrollHeight).toBeGreaterThan(metrics.clientHeight)
    }
    expect(metrics.scroll).toBe(metrics.client)

    const clippedElements = async (selector: string) => page.locator(selector).evaluateAll((elements) => {
      const documentWidth = document.documentElement.clientWidth
      const documentHeight = Math.max(
        document.documentElement.clientHeight,
        document.documentElement.scrollHeight,
      )

      return elements.flatMap((element) => {
        const rect = element.getBoundingClientRect()
        const style = getComputedStyle(element)
        if (
          style.display === 'none' ||
          style.visibility === 'hidden' ||
          rect.width === 0 ||
          rect.height === 0
        ) return []

        const top = rect.top + window.scrollY
        const bottom = rect.bottom + window.scrollY
        const clipped = rect.left < -0.5 ||
          rect.right > documentWidth + 0.5 ||
          top < -0.5 ||
          bottom > documentHeight + 0.5
        if (!clipped) return []

        const label = element.getAttribute('aria-label') ??
          element.textContent?.trim() ??
          element.tagName.toLowerCase()
        return [`${element.tagName.toLowerCase()} "${label}" at ${JSON.stringify(rect.toJSON())}`]
      })
    })

    const clippedControls = await clippedElements(controlSelector)
    const clippedText = await clippedElements(visibleTextSelector)

    expect(clippedControls).toEqual([])
    expect(clippedText).toEqual([])

    const navigation = page.getByRole('navigation', { name: 'Primary navigation' })
    await expect(navigation.locator('.MuiListSubheader-root')).toHaveCount(0)
    await expect(navigation.locator('.MuiList-root')).toHaveCount(1)
    const navigationLinks = navigation.getByRole('link')
    await expect(navigationLinks).toHaveCount(6)
    await expect(navigationLinks).toHaveText([
      'Overview',
      'Sensors',
      'Alerts',
      'EDA',
      'Model Evaluation',
      'System Health',
    ])
    expect(await navigationLinks.evaluateAll((links) =>
      links.every((link) => link.querySelectorAll('.MuiSvgIcon-root').length === 1),
    )).toBe(true)
    const navigationFonts = await navigationLinks.locator('.MuiListItemText-primary').evaluateAll((elements) =>
      elements.map((element) => getComputedStyle(element).fontFamily),
    )
    for (const font of navigationFonts) expect(font).toContain('Inter')
    const navigationPaddings = await navigationLinks.evaluateAll((links) =>
      links.map((link) => {
        const style = getComputedStyle(link)
        return { left: style.paddingLeft, right: style.paddingRight }
      }),
    )
    for (const padding of navigationPaddings) expect(padding).toEqual({ left: '16px', right: '16px' })

    switch (name) {
      case 'Overview': {
        const navigation = page.locator('.MuiDrawer-paper')
        const main = page.locator('main')
        const [navigationBox, mainBox] = await Promise.all([
          navigation.boundingBox(),
          main.boundingBox(),
        ])
        expect(navigationBox).not.toBeNull()
        expect(mainBox).not.toBeNull()
        if (navigationBox !== null && mainBox !== null) {
          expect(Math.abs(navigationBox.width - 264)).toBeLessThanOrEqual(layoutTolerance)
          expect(Math.abs(mainBox.x - 264)).toBeLessThanOrEqual(layoutTolerance)
        }

        const currentAlertActionLinks = page
          .getByRole('region', { name: 'Current alert for n4' })
          .getByRole('link')
        await expect(currentAlertActionLinks).toHaveCount(2)
        const currentAlertActionHeights = await currentAlertActionLinks.evaluateAll((nodes) =>
          nodes.map((node) => node.getBoundingClientRect().height),
        )
        for (const height of currentAlertActionHeights) expect(height).toBeLessThan(44)

        const summary = page.getByRole('region', { name: 'Operational summary' })
        const summaryValues = summary.locator('h2')
        await expect(summaryValues).toHaveCount(4)
        await expectWithinBounds(summaryValues, summary)

        const sensorCards = page.getByRole('article', { name: /^Sensor n[1-6]$/ })
        await expect(sensorCards).toHaveCount(6)
        const inspectLinks = sensorCards.getByRole('link', { name: 'Inspect sensor history' })
        const reviewLinks = sensorCards.getByRole('link', { name: /^Review/ })
        const matrixActions = sensorCards.getByRole('link')
        await expect(inspectLinks).toHaveCount(6)
        await expect(reviewLinks).toHaveCount(1)
        await expect(matrixActions).toHaveCount(7)
        await expect(
          page.getByRole('article', { name: 'Sensor n4' }).getByRole('link', { name: /^Review/ }),
        ).toHaveCount(1)
        for (const card of await sensorCards.all()) {
          const actions = card.getByRole('link')
          await expectWithinBounds(card.locator('h3, p, dt, dd, a'), card)
          await expectWithinBounds(actions, card)
          expect(await actions.evaluateAll((nodes) =>
            nodes.every((node) => node.parentElement === nodes[0]?.parentElement),
          )).toBe(true)
          await expect(actions.first().locator('..')).toHaveCSS('flex-wrap', 'wrap')
          const actionHeights = await actions.evaluateAll((nodes) =>
            nodes.map((node) => node.getBoundingClientRect().height),
          )
          for (const height of actionHeights) expect(height).toBeGreaterThanOrEqual(44)
        }
        break
      }
      case 'Sensor Detail & History': {
        const filters = page.getByRole('group', { name: 'Temporal filters' })
        const history = page.getByRole('region', { name: 'Telemetry and inference history' })
        const relatedHistory = page.getByRole('region', { name: 'Related alert history' })
        await expectWithinBounds(filters.locator('label, input, select'), page.locator('main > div'))
        await expectWithinBounds(history.locator(visibleTextSelector), history)
        await expectWithinBounds(relatedHistory.locator(visibleTextSelector), relatedHistory)

        const relatedEvents = relatedHistory.getByRole('article')
        expect(await relatedEvents.count()).toBeGreaterThan(0)
        for (const event of await relatedEvents.all()) {
          await expectWithinBounds(event.locator('h3, p'), event)
        }

        const dialogTrigger = history.getByRole('button', { name: 'Lihat data', exact: true })
        await dialogTrigger.click()
        const dialog = page.getByRole('dialog', { name: 'History data for n4' })
        await expect(dialog).toBeVisible()
        await expectWithinBounds(
          dialog.locator('[role="columnheader"]:visible, [role="gridcell"]:visible'),
          dialog,
        )
        await dialog.getByRole('button', { name: 'Close' }).click()
        await expect(dialog).toBeHidden()
        await expect(dialogTrigger).toBeFocused()
        break
      }
      case 'Alerts': {
        const filters = page.getByRole('group', { name: 'Alert filters' })
        const filterRegion = page.getByRole('region', { name: 'Alert filters' })
        const grid = page.getByRole('grid', { name: 'Current alerts' })
        const headers = grid.getByRole('columnheader')
        const technicalCells = grid.locator([
          '.MuiDataGrid-cell[data-field="alert_id"]:visible',
          '.MuiDataGrid-cell[data-field="device_id"]:visible',
          '.MuiDataGrid-cell[data-field="latest_event_ts"]:visible',
        ].join(','))
        const actions = grid.locator('.MuiDataGrid-cell[data-field="actions"] button:visible')
        const gridContainer = grid.locator('..')
        const pagination = gridContainer.getByRole('combobox', { name: 'Rows per page:' })
        const immutableHistory = page.getByRole('region', { name: 'Immutable alert event history' })
        const immutableHistoryState = immutableHistory.getByRole('status', {
          name: 'No alert events returned',
        })

        await expectWithinBounds(filters.locator('label, input, select'), filterRegion)
        await expect(headers).toHaveCount(5)
        await expectWithinBounds(headers, grid)
        await expectWithinBounds(technicalCells, grid)
        await expectWithinBounds(actions, grid)
        await expectWithinBounds(pagination, gridContainer)
        await expectWithinBounds(immutableHistoryState, immutableHistory)
        await expectWithinBounds(immutableHistory.locator(visibleTextSelector), immutableHistory)
        break
      }
      case 'EDA': {
        const temporalFilters = page.getByRole('group', { name: 'Temporal filters' })
        const sensorLabel = temporalFilters.locator('label').filter({ hasText: 'Sensor' })
        await expect(sensorLabel).toHaveAttribute('data-shrink', 'true')

        const distributions = page.getByRole('group', { name: 'Distribution panels' })
        const articles = distributions.getByRole('article')
        await expect(articles).toHaveCount(3)
        await expect(distributions.getByRole('article', { name: 'Temperature distribution', exact: true })).toBeVisible()
        await expect(distributions.getByRole('article', { name: 'Relative humidity distribution', exact: true })).toBeVisible()
        await expect(distributions.getByRole('article', { name: 'Anomaly score distribution', exact: true })).toBeVisible()
        expect(await gridColumnCount(distributions)).toBe(testInfo.project.name === 'desktop-1280' ? 2 : 3)
        break
      }
      case 'Model Evaluation': {
        const charts = page.getByRole('group', { name: 'Labeled evaluation charts' })
        const articles = charts.getByRole('article')
        await expect(articles).toHaveCount(3)
        await expect(charts.getByRole('article', { name: 'Confusion matrix', exact: true })).toBeVisible()
        await expect(charts.getByRole('article', { name: 'ROC curve', exact: true })).toBeVisible()
        await expect(charts.getByRole('article', { name: 'Precision recall curve', exact: true })).toBeVisible()
        expect(await gridColumnCount(charts)).toBe(testInfo.project.name === 'desktop-1920' ? 3 : 2)

        const metadata = page.getByRole('region', { name: 'Artifact identity and metadata' })
        const modelHash = metadata.locator('dt', { hasText: 'Model hash:' }).locator('..').locator('dd')
        await expect(modelHash).toBeVisible()
        expect(await modelHash.evaluate((element) => getComputedStyle(element).fontFamily)).toContain('IBM Plex Mono')
        break
      }
      case 'System Health': {
        const freshness = page.getByRole('group', { name: 'Freshness snapshot' })
        const statusPoll = freshness.getByRole('region', { name: 'Status-poll freshness' })
        const telemetry = freshness.getByRole('region', { name: 'Telemetry freshness' })
        const [statusPollBox, telemetryBox] = await Promise.all([
          statusPoll.boundingBox(),
          telemetry.boundingBox(),
        ])
        expect(statusPollBox).not.toBeNull()
        expect(telemetryBox).not.toBeNull()
        if (statusPollBox !== null && telemetryBox !== null) {
          expect(Math.abs(statusPollBox.y - telemetryBox.y)).toBeLessThanOrEqual(layoutTolerance)
        }

        const serviceTable = page.getByRole('table', { name: 'Service liveness and readiness' })
        const tableContainer = serviceTable.locator('..')
        await expect(serviceTable).toBeVisible()
        await expectWithinBounds(serviceTable.locator('caption, th, td'), tableContainer)
        break
      }
    }
  })
}

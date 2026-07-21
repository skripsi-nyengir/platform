import {
  expect,
  expectVisibleFocus,
  gotoScenario,
  tabTo,
  test,
} from './helpers'

const from = '2026-07-19T10:00:00Z'
const to = '2026-07-19T10:30:00Z'

test('keyboard focus stays visible through navigation, filters, grids, actions, and dialog', async ({ page }) => {
  await gotoScenario(
    page,
    `/sensors/n5?sensor=n5&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&bucket=5m`,
    'data-gap',
  )

  const overviewLink = page.getByRole('link', { name: 'Overview' })
  await tabTo(page, overviewLink)
  await expectVisibleFocus(overviewLink)

  const sensorFilter = page.getByRole('combobox', { name: 'Sensor' })
  await tabTo(page, sensorFilter)
  await expectVisibleFocus(sensorFilter)

  const dataButton = page.getByRole('button', { name: 'Lihat data' })
  await tabTo(page, dataButton)
  await expectVisibleFocus(dataButton)
  await page.keyboard.press('Enter')

  const dialog = page.getByRole('dialog', { name: 'History data for n5' })
  await expect(dialog).toBeVisible()
  const close = dialog.getByRole('button', { name: 'Close' })
  await tabTo(page, close)
  await expectVisibleFocus(close)
  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()

  await gotoScenario(
    page,
    '/alerts?from=2026-07-19T10%3A00%3A00Z&to=2026-07-19T11%3A00%3A00Z',
    'active-anomaly',
  )
  const alertsLink = page.getByRole('link', { name: 'Alerts' })
  await tabTo(page, alertsLink)
  await expectVisibleFocus(alertsLink)
  await page.keyboard.press('Enter')
  await expect(page.getByRole('heading', { level: 1, name: 'Alerts' })).toBeVisible()

  const alertFilter = page.getByRole('combobox', { name: 'Sensor' })
  await tabTo(page, alertFilter)
  await expectVisibleFocus(alertFilter)

  const grid = page.getByRole('grid', { name: 'Current alerts' })
  const alertColumn = grid.getByRole('columnheader', { name: 'Alert ID' })
  await tabTo(page, alertColumn)
  await expectVisibleFocus(alertColumn)
  await page.keyboard.press('ArrowDown')
  const alertCell = grid.getByRole('gridcell', { name: 'alert_n4_active' })
  await expectVisibleFocus(alertCell)
  await page.keyboard.press(' ')
  await expect(page.getByRole('region', { name: 'Immutable alert event history' })).toBeVisible()

  const acknowledge = page.getByRole('button', { name: 'Acknowledge alert' })
  await tabTo(page, acknowledge)
  await expectVisibleFocus(acknowledge)
})

test('overview sparklines contain no tabbable chart proxies', async ({ page }) => {
  await gotoScenario(page, '/', 'active-anomaly')

  const charts = page.getByRole('img', {
    name: /Recent (Temperature|RH) history for sensor/,
  })
  await expect(charts).toHaveCount(12)
  await expect(charts.locator('[tabindex="0"]')).toHaveCount(0)
})

test('keyboard opens and closes model evaluation chart data dialogs', async ({ page }) => {
  await gotoScenario(page, '/model-evaluation?model_version=model-v2', 'active-anomaly')

  const confusionMatrixData = page.getByRole('button', { name: 'Lihat data Confusion matrix' })
  await expect(confusionMatrixData).toBeVisible()
  await tabTo(page, confusionMatrixData)
  await expectVisibleFocus(confusionMatrixData)
  await page.keyboard.press('Enter')
  const confusionMatrixDialog = page.getByRole('dialog', { name: 'Confusion matrix data' })
  await expect(confusionMatrixDialog).toBeVisible()
  const confusionMatrixClose = confusionMatrixDialog.getByRole('button', { name: 'Close' })
  await tabTo(page, confusionMatrixClose)
  await expectVisibleFocus(confusionMatrixClose)
  await page.keyboard.press('Escape')
  await expect(confusionMatrixDialog).toBeHidden()
  await expectVisibleFocus(confusionMatrixData)

  const rocCurveData = page.getByRole('button', { name: 'Lihat data ROC curve' })
  await expect(rocCurveData).toBeVisible()
  await tabTo(page, rocCurveData)
  await expectVisibleFocus(rocCurveData)
  await page.keyboard.press('Enter')
  const rocCurveDialog = page.getByRole('dialog', { name: 'ROC curve data; AUC 0.97' })
  await expect(rocCurveDialog).toBeVisible()
  const rocCurveClose = rocCurveDialog.getByRole('button', { name: 'Close' })
  await tabTo(page, rocCurveClose)
  await expectVisibleFocus(rocCurveClose)
  await page.keyboard.press('Escape')
  await expect(rocCurveDialog).toBeHidden()
  await expectVisibleFocus(rocCurveData)

  const precisionRecallCurveData = page.getByRole('button', {
    name: 'Lihat data Precision recall curve',
  })
  await expect(precisionRecallCurveData).toBeVisible()
  await tabTo(page, precisionRecallCurveData)
  await expectVisibleFocus(precisionRecallCurveData)
  await page.keyboard.press('Enter')
  const precisionRecallCurveDialog = page.getByRole('dialog', {
    name: 'Precision recall curve data; average precision 0.93',
  })
  await expect(precisionRecallCurveDialog).toBeVisible()
  const precisionRecallCurveClose = precisionRecallCurveDialog.getByRole('button', { name: 'Close' })
  await tabTo(page, precisionRecallCurveClose)
  await expectVisibleFocus(precisionRecallCurveClose)
  await page.keyboard.press('Escape')
  await expect(precisionRecallCurveDialog).toBeHidden()
  await expectVisibleFocus(precisionRecallCurveData)
})

import {
  disableAppQueryRetries,
  expect,
  failNextAppFetch,
  gotoScenario,
  test,
} from './helpers'

const from = '2026-07-19T10:00:00Z'
const to = '2026-07-19T10:30:00Z'

test('operator inspects a documented gap and its bounded table alternative', async ({ page }) => {
  await gotoScenario(
    page,
    `/sensors/n5?sensor=n5&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&bucket=5m`,
    'data-gap',
  )

  await expect(page.getByRole('combobox', { name: 'Sensor' })).toHaveValue('n5')
  await expect(page.getByRole('textbox', { name: 'From' })).toHaveValue(from)
  await expect(page.getByRole('textbox', { name: 'To' })).toHaveValue(to)
  await expect(page.getByRole('combobox', { name: 'Bucket' })).toHaveValue('5m')
  await expect(page.locator('p:visible').filter({ hasText: /1 documented gap\./ })).toBeVisible()

  await page.getByRole('button', { name: 'Lihat data' }).click()
  const dialog = page.getByRole('dialog', { name: 'History data for n5' })
  await expect(dialog).toContainText('9 bounded records returned')
  await expect(dialog.getByRole('gridcell', { name: 'Yes' })).toBeVisible()
  await expect(dialog.getByRole('gridcell', {
    name: '2026-07-19T10:15:00Z – 2026-07-19T10:20:00Z',
  })).toBeVisible()
  await dialog.getByRole('button', { name: 'Close' }).click()
  await expect(dialog).toBeHidden()
})

test('operator retries a failed sensor-history request after changing a filter', async ({ page }) => {
  await gotoScenario(
    page,
    `/sensors/n4?sensor=n4&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&bucket=5m`,
    'active-anomaly',
  )

  const telemetry = page.getByRole('region', { name: 'Telemetry history' })
  await expect(telemetry).toContainText('6 bounded telemetry records')
  await disableAppQueryRetries(page)
  await failNextAppFetch(page, '/api/telemetry/history')

  await page.getByRole('combobox', { name: 'Bucket' }).selectOption('raw')
  await expect(page.getByRole('combobox', { name: 'Bucket' })).toHaveValue('raw')
  const error = telemetry.getByRole('alert')
  await expect(error).toContainText('Deterministic browser failure for /api/telemetry/history')

  await error.getByRole('button', { name: 'Retry' }).click()
  await expect(telemetry).toContainText('6 bounded telemetry records')
  await expect(error).toBeHidden()
})

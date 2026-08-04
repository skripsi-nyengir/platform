import { b02DeviceId, expect, gotoScenario, test } from './helpers'

test('overview exposes one B02 sensor with result-driven provenance', async ({ page }) => {
  const historyRequest = page.waitForRequest((request) =>
    new URL(request.url()).pathname === '/api/telemetry/history',
  )
  await gotoScenario(page, '/', 'active-anomaly')
  const historyUrl = new URL((await historyRequest).url())
  expect(historyUrl.searchParams.get('from')).toBe('2026-07-19T16:30:00')
  expect(historyUrl.searchParams.get('to')).toBe('2026-07-19T17:30:00')
  expect(historyUrl.searchParams.get('bucket')).toBe('raw')
  expect(historyUrl.searchParams.get('limit')).toBe('5000')
  const sensor = page.getByRole('article', { name: 'Sensor B02' })
  await expect(sensor).toBeVisible()
  await expect(sensor.getByText('Simulasi preview')).toBeVisible()
  await sensor.getByRole('link', { name: 'Inspect sensor history' }).click()
  await expect(page).toHaveURL(new RegExp(`/sensors/${b02DeviceId}`))
})

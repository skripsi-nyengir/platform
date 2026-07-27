import { b02DeviceId, expect, gotoScenario, test } from './helpers'

test('overview exposes one B02 sensor with result-driven provenance', async ({ page }) => {
  await gotoScenario(page, '/', 'active-anomaly')
  const sensor = page.getByRole('article', { name: 'Sensor B02' })
  await expect(sensor).toBeVisible()
  await expect(sensor.getByText('Simulasi preview')).toBeVisible()
  await sensor.getByRole('link', { name: 'Inspect sensor history' }).click()
  await expect(page).toHaveURL(new RegExp(`/sensors/${b02DeviceId}`))
})

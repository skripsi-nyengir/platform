import { b02DeviceId, b02From, b02To, expect, gotoScenario, test } from './helpers'

test('sensor detail uses B02 identity, WIB bounds, and API provenance', async ({ page }) => {
  await gotoScenario(
    page,
    `/sensors/${b02DeviceId}?sensor=${b02DeviceId}&from=${b02From}&to=${b02To}&bucket=raw`,
    'active-anomaly',
  )
  await expect(page.getByRole('combobox', { name: 'Sensor' })).toHaveValue(b02DeviceId)
  await expect(page.getByText('Simulasi preview').first()).toBeVisible()
  await expect(page.getByRole('region', { name: 'Related alert history' }))
    .toContainText('2026-06-01T00:00:05Z')
})

for (const retiredId of ['talpha-1', 'talpha-2', 'n1', 'n2', 'n3', 'n4', 'n5', 'n6']) {
  test(`redirects retired sensor ${retiredId}`, async ({ page }) => {
    await page.goto(`/sensors/${retiredId}`)
    await expect(page).toHaveURL('/')
  })
}

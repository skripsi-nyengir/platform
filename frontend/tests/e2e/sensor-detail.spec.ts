import { b02DeviceId, expect, gotoScenario, test } from './helpers'

test('sensor detail uses B02 identity, WIB bounds, and API provenance', async ({ page }) => {
  await gotoScenario(
    page,
    `/sensors/${b02DeviceId}`,
    'active-anomaly',
  )
  await expect(page.getByRole('combobox', { name: 'Sensor' })).toHaveValue(b02DeviceId)
  await expect(page.getByRole('textbox', { name: 'From' })).toHaveValue('2026-02-01T00:00:00')
  await expect(page.getByRole('textbox', { name: 'To' })).toHaveValue('2026-06-01T00:00:00')
  await expect(page.getByRole('combobox', { name: 'Bucket' })).toHaveValue('1d')
  await expect(page.getByText('120 bounded telemetry records')).toBeVisible()
  await expect(page.getByText(/View truncated/)).toHaveCount(0)
  await expect(page.getByText('Simulasi preview').first()).toBeVisible()
  await expect(page.getByRole('region', { name: 'Related alert history' }))
    .toContainText('2026-06-01T00:00:05Z')
})

test('sensor detail discloses a truncated fine-bucket response', async ({ page }) => {
  await gotoScenario(page, `/sensors/${b02DeviceId}?bucket=15m`, 'normal')

  await expect(page.getByText('2000 bounded telemetry records')).toBeVisible()
  await expect(page.getByRole('note')).toContainText(
    'View truncated. Pilih rentang lebih sempit atau bucket lebih kasar untuk melihat seluruh data.',
  )
})

for (const retiredId of ['talpha-1', 'talpha-2', 'n1', 'n2', 'n3', 'n4', 'n5', 'n6']) {
  test(`redirects retired sensor ${retiredId}`, async ({ page }) => {
    await page.goto(`/sensors/${retiredId}`)
    await expect(page).toHaveURL('/')
  })
}

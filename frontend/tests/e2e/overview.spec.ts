import { expect, gotoScenario, test } from './helpers'

test('operator triages the active n4 anomaly from Overview', async ({ page }) => {
  await gotoScenario(page, '/', 'active-anomaly')

  await expect(page.getByRole('heading', { level: 1, name: 'Overview' })).toBeVisible()
  const summary = page.getByRole('region', { name: 'Operational summary' })
  await expect(summary).toContainText('Active alerts')
  await expect(summary).toContainText('1')
  await expect(summary).toContainText('+0.16 · n4')

  const alert = page.getByRole('region', { name: 'Current alert for n4' })
  await expect(alert.getByRole('heading', { name: 'Sensor n4' })).toBeVisible()
  await expect(alert).toContainText('Active anomaly')
  await expect(alert.getByRole('button', { name: 'Acknowledge alert' })).toBeEnabled()

  const sensor = page.getByRole('article', { name: 'Sensor n4' })
  await sensor.getByRole('link', { name: 'Inspect sensor history' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Sensor Detail & History' })).toBeVisible()
  await expect(page.getByText('Selected sensor: n4')).toBeVisible()
  await expect(page.getByRole('combobox', { name: 'Sensor' })).toHaveValue('n4')
  await expect(page.getByRole('region', { name: 'Related alert history' })).toBeVisible()
})

test('operator reviews the active n4 alert from Overview', async ({ page }) => {
  await gotoScenario(page, '/', 'active-anomaly')

  const alert = page.getByRole('region', { name: 'Current alert for n4' })
  await alert.getByRole('link', { name: 'Review active alert' }).click()

  await expect(page).toHaveURL(/\/alerts\?sensor=n4$/)
  await expect(page.getByRole('heading', { level: 1, name: 'Alerts' })).toBeVisible()
  await expect(page.getByRole('combobox', { name: 'Sensor' })).toHaveValue('n4')
})

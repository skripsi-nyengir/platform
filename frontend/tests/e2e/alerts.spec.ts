import { expect, gotoScenario, test } from './helpers'

test('selected alert lifecycle remains visible outside corpus-time bounds', async ({ page }) => {
  await gotoScenario(page, '/alerts?from=2026-02-01T00:00:00&to=2026-03-01T00:00:00', 'active-anomaly')
  const grid = page.getByRole('grid', { name: 'Current alerts' })
  await grid.getByRole('gridcell', { name: 'alert_b02_preview_active' }).click()
  const history = page.getByRole('region', { name: 'Alert event history' })
  await expect(history).toContainText('2026-06-01T00:00:05Z')
  await expect(history.getByText('Simulasi preview')).toBeVisible()
})

test('operator completes acknowledge and resolve lifecycle', async ({ page }) => {
  await gotoScenario(page, '/alerts', 'active-anomaly')
  await page.getByRole('button', { name: 'Acknowledge alert' }).click()
  await expect(page.getByRole('button', { name: 'Resolve alert' })).toBeEnabled()
  await page.getByRole('button', { name: 'Resolve alert' }).click()
  await expect(page.getByRole('gridcell', { name: 'resolved' })).toBeVisible()
})

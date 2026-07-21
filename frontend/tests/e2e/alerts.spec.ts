import { expect, gotoScenario, setBrowserTime, test } from './helpers'

test('operator acknowledges and then resolves an alert without skipping lifecycle state', async ({ page }) => {
  await gotoScenario(
    page,
    '/alerts?from=2026-07-19T10%3A00%3A00Z&to=2026-07-19T11%3A00%3A00Z',
    'active-anomaly',
  )

  const grid = page.getByRole('grid', { name: 'Current alerts' })
  await expect(grid.getByRole('gridcell', { name: 'Active', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Acknowledge alert' }).click()

  const resolve = page.getByRole('button', { name: 'Resolve alert' })
  await expect(resolve).toBeEnabled()
  await expect(grid.getByRole('gridcell', { name: 'acknowledged' })).toBeVisible()

  await setBrowserTime(page, '2026-07-19T10:31:00Z')
  await resolve.click()
  await expect(grid.getByRole('gridcell', { name: 'resolved' })).toBeVisible()
  await expect(page.getByRole('button', { name: /alert$/i })).toHaveCount(0)

  await grid.getByRole('gridcell', { name: 'alert_n4_active' }).click()
  const history = page.getByRole('region', { name: 'Immutable alert event history' })
  await expect(history.getByRole('listitem')).toHaveCount(3)
  await expect(history).toContainText('Detected')
  await expect(history).toContainText('Acknowledged')
  await expect(history).toContainText('Resolved')
})

test('direct active resolve through in-page fetch returns the lifecycle 409', async ({ page }) => {
  await gotoScenario(page, '/alerts', 'active-anomaly')
  await expect(page.getByRole('button', { name: 'Acknowledge alert' })).toBeEnabled()

  const result = await page.evaluate(async () => {
    const response = await fetch('/api/alerts/alert_n4_active/resolve', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        command_id: '550e8400-e29b-41d4-a716-446655440000',
        event_ts: new Date().toISOString(),
      }),
    })
    return { body: await response.json(), status: response.status }
  })

  expect(result.status).toBe(409)
  expect(result.body).toMatchObject({
    request_id: 'req_direct_resolve',
    status: 409,
    title: 'Lifecycle conflict',
  })
  await expect(page.getByRole('button', { name: 'Acknowledge alert' })).toBeEnabled()
  await expect(page.getByRole('button', { name: 'Resolve alert' })).toHaveCount(0)
})

import {
  disableAppQueryRetries,
  expect,
  failNextAppFetch,
  gotoScenario,
  refetchAppQuery,
  setBrowserTime,
  test,
} from './helpers'

test('failed status poll retains the snapshot and recovers through Retry', async ({ page }) => {
  await gotoScenario(page, '/system-health', 'normal')

  const snapshot = page.getByRole('region', { name: 'Latest known system snapshot' })
  await expect(snapshot).toContainText('Snapshot checked at: 2026-07-19T10:30:00Z')
  await expect(snapshot).toContainText('Telemetry age: 20 seconds')
  await expect(page.getByRole('table', { name: 'Service liveness and readiness' })).toBeVisible()

  await setBrowserTime(page, '2026-07-19T10:31:00Z')
  await disableAppQueryRetries(page)
  await failNextAppFetch(page, '/api/system/status')
  await refetchAppQuery(page, ['system', 'status'])

  const failure = page.getByRole('alert')
  await expect(failure).toContainText('System status refresh failed')
  await expect(page.getByText('Current reachability: Unknown')).toBeVisible()
  await expect(snapshot).toContainText('Snapshot checked at: 2026-07-19T10:30:00Z')
  await expect(page.getByRole('table', { name: 'Service liveness and readiness' })).toBeVisible()

  await failure.getByRole('button', { name: 'Retry' }).click()
  await expect(page.getByText('Current reachability: Unknown')).toBeHidden()
  await expect(failure).toBeHidden()
  await expect(snapshot).toContainText('Displayed at: 2026-07-19T10:31:00.000Z')
})

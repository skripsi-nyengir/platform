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

  const currentDashboard = page.getByRole('region', { name: 'System health current snapshot' })
  const liveHealth = currentDashboard.getByRole('region', { name: 'Live telemetry health' })
  await expect(liveHealth.getByText('Healthy', { exact: true })).toBeVisible()
  const freshness = liveHealth.getByRole('article', { name: 'Sensor freshness' })
  await expect(freshness).toContainText('1Fresh')
  await expect(freshness).toContainText('0Stale')
  await expect(freshness).toContainText('0Offline')
  const evidence = currentDashboard.getByRole('region', { name: 'Snapshot evidence' })
  await expect(evidence).toContainText('Status checked (UTC)')
  await expect(evidence).toContainText('2026-07-24T08:00:00Z')
  await expect(evidence).toContainText('Latest telemetry (Asia/Jakarta, WIB)')
  await expect(evidence).toContainText('2026-07-31T07:59:59')
  const services = currentDashboard.getByRole('region', { name: 'Service status' })
  await expect(services).toBeVisible()
  await expect(services.getByRole('article')).toHaveCount(5)
  await expect(services.getByRole('heading', { name: 'Telemetry import' })).toHaveCount(0)
  await expect(services.getByRole('heading', { name: 'Original artifact readiness' })).toHaveCount(0)

  await setBrowserTime(page, '2026-07-19T10:31:00Z')
  await disableAppQueryRetries(page)
  await failNextAppFetch(page, '/api/system/status')
  await refetchAppQuery(page, ['system', 'status'])

  const retainedDashboard = page.getByRole('region', {
    name: 'System health retained last known snapshot',
  })
  await expect(retainedDashboard.getByText('Current reachability: Unknown')).toBeVisible()
  await expect(retainedDashboard).toContainText('Status checked (UTC)')
  await expect(retainedDashboard).toContainText('2026-07-24T08:00:00Z')
  await expect(retainedDashboard.getByText('Last known · Healthy')).toBeVisible()
  await expect(retainedDashboard.getByText('Liveness: Last known · Alive').first()).toBeVisible()
  await expect(page.getByRole('region', { name: 'System health current snapshot' })).toBeHidden()

  await retainedDashboard.getByRole('button', { name: 'Retry' }).click()
  await expect(page.getByText('Current reachability: Unknown')).toBeHidden()
  const recoveredDashboard = page.getByRole('region', { name: 'System health current snapshot' })
  await expect(recoveredDashboard).toContainText('Snapshot displayed (UTC)')
  await expect(recoveredDashboard).toContainText('2026-07-19T10:31:00.000Z')
})

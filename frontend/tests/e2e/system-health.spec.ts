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
  await expect(snapshot).toContainText('Status checked at (UTC): 2026-07-24T08:00:00Z')
  await expect(snapshot).toContainText('Historical corpus latest timestamp: 2026-05-31T23:59:59')
  await expect(snapshot).toContainText('Fresh sensors: 1; stale sensors: 0; offline sensors: 0')
  await expect(snapshot).toContainText('Asia/Jakarta (WIB)')
  const services = page.getByRole('table', { name: 'Preview component readiness' })
  await expect(services).toBeVisible()
  await expect(services.getByRole('rowheader')).toHaveCount(5)

  await setBrowserTime(page, '2026-07-19T10:31:00Z')
  await disableAppQueryRetries(page)
  await failNextAppFetch(page, '/api/system/status')
  await refetchAppQuery(page, ['system', 'status'])

  const failure = page.getByRole('alert')
  await expect(failure).toContainText('System status refresh failed')
  await expect(page.getByText('Current reachability: Unknown')).toBeVisible()
  await expect(snapshot).toContainText('Status checked at (UTC): 2026-07-24T08:00:00Z')
  await expect(services).toBeVisible()

  await failure.getByRole('button', { name: 'Retry' }).click()
  await expect(page.getByText('Current reachability: Unknown')).toBeHidden()
  await expect(failure).toBeHidden()
  await expect(snapshot).toContainText('Displayed at: 2026-07-19T10:31:00.000Z')
})

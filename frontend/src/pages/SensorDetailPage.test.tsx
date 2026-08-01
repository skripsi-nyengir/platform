import '@testing-library/jest-dom/vitest'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { queryClient } from '../app/queryClient'
import type { CurrentAlertsResponse } from '../contracts/alerts'
import { activeDetectedAlert } from '../mocks/fixtures/alerts'
import { server } from '../mocks/node'
import { renderApp } from '../test/renderApp'

afterEach(() => {
  queryClient.clear()
  vi.restoreAllMocks()
})

describe('SensorDetailPage', () => {
  it('restores custom live bounds and renders current Task 9 data', async () => {
    renderApp(
      '/sensors/b02f3872-ruang-produksi?range=custom&from=2026-07-31T06:00:00&to=2026-07-31T08:00:00',
    )
    expect(await screen.findByRole('combobox', { name: 'Range' })).toHaveValue('custom')
    expect(screen.getByRole('textbox', { name: 'From' })).toHaveValue('2026-07-31T06:00:00')
    expect(screen.getByRole('textbox', { name: 'To' })).toHaveValue('2026-07-31T08:00:00')
    expect(await screen.findByText('Latest score: 0.58')).toBeVisible()
    expect(screen.getByText('Severity: info')).toBeVisible()
    expect(screen.getByText('Live health: healthy')).toBeVisible()
    expect(await screen.findByText(/bounded telemetry records/)).toBeVisible()
  })

  it('lazily loads episode context and supports manual acknowledge then resolve', async () => {
    const user = userEvent.setup()
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    renderApp('/sensors/b02f3872-ruang-produksi?range=1h&__scenario=active-anomaly')

    expect(await screen.findByRole('heading', { name: 'Active alerts (1)' })).toBeVisible()
    expect(screen.getByText('Start 31 May 2026, 23:51:30')).toBeVisible()
    expect(screen.getByText('End 31 May 2026, 23:52:30')).toBeVisible()
    expect(fetchSpy.mock.calls.some(([input]) =>
      new URL(String(input), 'http://localhost').pathname === '/api/alerts/alert_b02_preview_active',
    )).toBe(false)
    await user.click(screen.getByRole('button', { name: /Show episode context for/ }))
    expect(await screen.findByRole('heading', { name: 'Episode context' })).toBeVisible()
    await waitFor(() => expect(screen.getByLabelText('Episode context'))
      .toHaveTextContent('10 source readings before the episode'))
    await waitFor(() => expect(fetchSpy.mock.calls.filter(([input]) =>
      new URL(String(input), 'http://localhost').pathname === '/api/alerts/alert_b02_preview_active',
    )).toHaveLength(1))
    expect(screen.getByText('Detected')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Acknowledge alert' }))
    await user.click(await screen.findByRole('button', { name: 'Resolve alert' }))
    expect(await screen.findByText('Resolved alert')).toBeVisible()
  })

  it('keeps additional active alerts behind a compact disclosure', async () => {
    const user = userEvent.setup()
    const alerts = Array.from({ length: 5 }, (_, index) => ({
      ...activeDetectedAlert,
      alert_id: `${activeDetectedAlert.alert_id}_${index + 1}`,
      latest_event_id: `${activeDetectedAlert.latest_event_id}_${index + 1}`,
    }))
    server.use(http.get('/api/alerts/current', ({ request }) => {
      const url = new URL(request.url)
      const body = {
        request_id: 'req_many_current_alerts',
        time_zone: 'Asia/Jakarta',
        generated_at: '2026-07-24T08:00:00Z',
        items: alerts,
        page: Number(url.searchParams.get('page')),
        page_size: Number(url.searchParams.get('page_size')),
        total: alerts.length,
      } satisfies CurrentAlertsResponse
      return HttpResponse.json(body)
    }))

    renderApp('/sensors/b02f3872-ruang-produksi?range=1h&__scenario=active-anomaly')

    expect(await screen.findByRole('heading', { name: 'Active alerts (5)' })).toBeVisible()
    expect(screen.getAllByRole('article', { name: /Current alert for/ })).toHaveLength(3)
    await user.click(screen.getByRole('button', { name: 'Show 2 more' }))
    expect(screen.getAllByRole('article', { name: /Current alert for/ })).toHaveLength(5)
    await user.click(screen.getByRole('button', { name: 'Show fewer alerts' }))
    expect(screen.getAllByRole('article', { name: /Current alert for/ })).toHaveLength(3)
  })
})

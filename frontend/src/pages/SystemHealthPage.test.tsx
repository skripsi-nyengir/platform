import { CssBaseline } from '@mui/material'
import { ThemeProvider } from '@mui/material/styles'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { systemStatus } from '../mocks/fixtures/systemHealth'
import { server } from '../mocks/node'
import {
  createQueryTestHarness,
  type QueryTestHarness,
} from '../test/queryTestUtils'
import { theme } from '../theme/theme'
import { SystemHealthPage } from './SystemHealthPage'

const origin = window.location.origin
const firstDisplayTime = '2026-07-19T10:30:05Z'
const retryTime = '2026-07-19T10:31:10Z'

let harness: QueryTestHarness

function Providers({ children }: { children: ReactNode }) {
  const QueryProvider = harness.wrapper
  return (
    <QueryProvider>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </QueryProvider>
  )
}

function renderPage() {
  return render(<SystemHealthPage />, { wrapper: Providers })
}

function problem() {
  return {
    type: 'https://example.invalid/problems/system-status-unavailable',
    title: 'System status unavailable',
    status: 503,
    detail: 'The current system status could not be reached',
    instance: '/api/system/status',
    request_id: 'req_system_status_failed',
  }
}

beforeEach(() => {
  harness = createQueryTestHarness()
  vi.spyOn(Date, 'now').mockReturnValue(Date.parse(firstDisplayTime))
})

afterEach(() => {
  harness.restore()
  vi.restoreAllMocks()
})

describe('SystemHealthPage', () => {
  it('shows the latest snapshot with distinct poll, telemetry, liveness, and readiness facts', async () => {
    renderPage()

    expect(screen.getByRole('heading', { level: 1, name: 'System Health' })).toBeVisible()
    const snapshot = await screen.findByRole('region', { name: 'Latest known system snapshot' })
    const freshness = within(snapshot).getByRole('group', { name: 'Freshness snapshot' })
    const poll = within(freshness).getByRole('region', { name: 'Status-poll freshness' })
    const telemetry = within(freshness).getByRole('region', { name: 'Telemetry freshness' })
    expect(poll).toHaveTextContent('Snapshot checked at: 2026-07-19T10:30:00Z')
    expect(poll).toHaveTextContent('Displayed at: 2026-07-19T10:30:05.000Z')
    expect(poll).toHaveTextContent('Status poll age: 0 seconds')
    expect(telemetry).toHaveTextContent('Telemetry latest timestamp: 2026-07-19T10:29:40Z')
    expect(telemetry).toHaveTextContent('Telemetry age: 20 seconds')
    expect(telemetry).toHaveTextContent('Fresh sensors: 6; stale sensors: 0; offline sensors: 0')
    expect(within(snapshot).getByRole('heading', { name: 'Status-poll freshness' })).toBeVisible()
    expect(within(snapshot).getByRole('heading', { name: 'Telemetry freshness' })).toBeVisible()

    const checkedAt = within(poll).getByText('2026-07-19T10:30:00Z')
    const checkedAtLine = checkedAt.parentElement
    if (!(checkedAtLine instanceof HTMLElement)) throw new Error('Expected checked-at prose parent')
    expect(getComputedStyle(checkedAtLine).fontFamily).toContain('Inter')
    expect(getComputedStyle(checkedAt).fontFamily).toContain('IBM Plex Mono')

    const table = screen.getByRole('table', { name: 'Service liveness and readiness' })
    expect(within(table).getByRole('columnheader', { name: 'Liveness' })).toBeVisible()
    expect(within(table).getByRole('columnheader', { name: 'Readiness' })).toBeVisible()
    const api = within(table).getByRole('row', { name: /api alive ready/i })
    expect(api).toHaveTextContent('2026-07-19T10:30:00Z')
    expect(api).toHaveTextContent('API is serving deterministic fixtures')
    expect(getComputedStyle(within(api).getByRole('rowheader', { name: 'api' })).fontFamily)
      .toContain('IBM Plex Mono')
    expect(getComputedStyle(within(api).getByRole('cell', { name: 'alive' })).fontFamily)
      .toContain('Inter')
    expect(getComputedStyle(within(api).getByRole('cell', { name: 'ready' })).fontFamily)
      .toContain('Inter')
    expect(getComputedStyle(within(api).getByText('2026-07-19T10:30:00Z')).fontFamily)
      .toContain('IBM Plex Mono')
    expect(
      getComputedStyle(within(api).getByText('API is serving deterministic fixtures')).fontFamily,
    ).toContain('Inter')
    expect(screen.queryByText(/overall health/i)).not.toBeInTheDocument()
    expect(screen.queryByText('All deterministic mock services are ready')).not.toBeInTheDocument()
  })

  it('groups status-poll and telemetry freshness under the latest snapshot', async () => {
    renderPage()

    const snapshot = await screen.findByRole('region', { name: 'Latest known system snapshot' })
    const freshness = within(snapshot).getByRole('group', { name: 'Freshness snapshot' })
    const poll = within(freshness).getByRole('region', { name: 'Status-poll freshness' })
    const telemetry = within(freshness).getByRole('region', { name: 'Telemetry freshness' })
    expect(poll).toHaveTextContent('Status poll age: 0 seconds')
    expect(telemetry).toHaveTextContent('Telemetry age: 20 seconds')
    expect(screen.getByRole('table', { name: 'Service liveness and readiness' })).toBeVisible()
  })

  it('keeps null telemetry fallbacks and an empty service table visible', async () => {
    server.use(
      http.get(`${origin}/api/system/status`, () =>
        HttpResponse.json({
          ...systemStatus,
          services: [],
          telemetry: {
            latest_ts: null,
            age_seconds: null,
            fresh_sensor_count: 0,
            stale_sensor_count: 0,
            offline_sensor_count: 0,
          },
        }),
      ),
    )
    renderPage()

    const snapshot = await screen.findByRole('region', { name: 'Latest known system snapshot' })
    const freshness = within(snapshot).getByRole('group', { name: 'Freshness snapshot' })
    const telemetry = within(freshness).getByRole('region', { name: 'Telemetry freshness' })
    expect(telemetry).toHaveTextContent('Telemetry latest timestamp: Unavailable')
    expect(telemetry).toHaveTextContent('Telemetry age: Unknown')
    expect(telemetry).toHaveTextContent('Fresh sensors: 0; stale sensors: 0; offline sensors: 0')
    expect(
      getComputedStyle(within(telemetry).getByText('Telemetry latest timestamp: Unavailable')).fontFamily,
    ).toContain('Inter')
    expect(
      getComputedStyle(within(telemetry).getByText('Telemetry age: Unknown')).fontFamily,
    ).toContain('Inter')

    const table = screen.getByRole('table', { name: 'Service liveness and readiness' })
    expect(table).toBeVisible()
    expect(within(table).getAllByRole('row')).toHaveLength(1)
  })

  it('retains the snapshot, marks current reachability unknown, and retries a failed refetch', async () => {
    const now = vi.mocked(Date.now)
    renderPage()
    await screen.findByRole('region', { name: 'Latest known system snapshot' })

    server.use(
      http.get(`${origin}/api/system/status`, () =>
        HttpResponse.json(problem(), { status: 503 }),
      ),
    )
    now.mockReturnValue(Date.parse(retryTime))
    await harness.queryClient.refetchQueries({ queryKey: ['system', 'status'], exact: true })

    expect(await screen.findByText('System status refresh failed')).toBeVisible()
    expect(screen.getByText('Current reachability: Unknown')).toBeVisible()
    const retained = screen.getByRole('region', { name: 'Latest known system snapshot' })
    const retainedFreshness = within(retained).getByRole('group', { name: 'Freshness snapshot' })
    const retainedPoll = within(retainedFreshness).getByRole('region', { name: 'Status-poll freshness' })
    const retainedTelemetry = within(retainedFreshness).getByRole('region', { name: 'Telemetry freshness' })
    expect(retainedPoll).toHaveTextContent('Snapshot checked at: 2026-07-19T10:30:00Z')
    expect(retainedPoll).toHaveTextContent('Status poll age: 65 seconds')
    expect(retainedTelemetry).toHaveTextContent('Telemetry age: 20 seconds')
    expect(screen.getByRole('table', { name: 'Service liveness and readiness' })).toBeVisible()

    server.use(
      http.get(`${origin}/api/system/status`, () =>
        HttpResponse.json({
          ...systemStatus,
          request_id: 'req_system_status_retry',
          checked_at: retryTime,
          telemetry: {
            ...systemStatus.telemetry,
            latest_ts: '2026-07-19T10:31:05Z',
            age_seconds: 5,
          },
        }),
      ),
    )
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))

    await waitFor(() => expect(screen.queryByText('Current reachability: Unknown')).not.toBeInTheDocument())
    const recovered = screen.getByRole('region', { name: 'Latest known system snapshot' })
    const recoveredFreshness = within(recovered).getByRole('group', { name: 'Freshness snapshot' })
    const recoveredPoll = within(recoveredFreshness).getByRole('region', { name: 'Status-poll freshness' })
    const recoveredTelemetry = within(recoveredFreshness).getByRole('region', { name: 'Telemetry freshness' })
    expect(recoveredPoll).toHaveTextContent(`Snapshot checked at: ${retryTime}`)
    expect(recoveredPoll).toHaveTextContent('Status poll age: 0 seconds')
    expect(recoveredTelemetry).toHaveTextContent('Telemetry age: 5 seconds')
  })
})

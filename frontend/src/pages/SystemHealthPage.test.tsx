import { ThemeProvider } from '@mui/material/styles'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { SystemStatusResponse } from '../contracts/systemHealth'
import { resolveStatusDisplayMeta, type StatusDisplayMeta } from '../features/systemHealth/displayMeta'
import { SystemHealthDashboard } from '../features/systemHealth/SystemHealthDashboard'
import { formatDuration } from '../features/systemHealth/duration'
import { systemStatus } from '../mocks/fixtures/systemHealth'
import { renderApp } from '../test/renderApp'
import { theme } from '../theme/theme'

function snapshotWith(overrides: Partial<SystemStatusResponse> = {}): SystemStatusResponse {
  return {
    ...structuredClone(systemStatus),
    ...overrides,
  }
}

function renderDashboard(snapshot: SystemStatusResponse, retained = false) {
  const display: StatusDisplayMeta = {
    displayedAt: '2026-08-04T10:00:00.000Z',
    pollAgeSeconds: retained ? 90 : 0,
    retained,
  }
  return render(
    <ThemeProvider theme={theme} defaultMode="dark" noSsr>
      <SystemHealthDashboard
        snapshot={snapshot}
        display={display}
      />
    </ThemeProvider>,
  )
}

describe('SystemHealthPage', () => {
  it('renders the route-specific dashboard with five runtime services in API order', async () => {
    renderApp('/system-health')

    const health = await screen.findByRole('region', { name: 'Live telemetry health' })
    expect(within(health).getByText('Healthy')).toBeVisible()
    expect(screen.getByText('Live telemetry is healthy.')).toBeVisible()
    const readiness = screen.getByRole('group', { name: 'Service readiness counts' })
    expect(within(readiness).getByText('Ready 5')).toBeVisible()
    expect(within(readiness).getByText('Not ready 0')).toBeVisible()
    expect(within(readiness).getByText('Unknown 0')).toBeVisible()

    const cards = screen.getByTestId('service-status-grid').querySelectorAll('[data-service-name]')
    expect([...cards].map((card) => card.getAttribute('data-service-name'))).toEqual([
      'api',
      'database',
      'live-subscriber',
      'preview-worker',
      'active-selection',
    ])
    expect(screen.queryByRole('heading', { name: 'Telemetry import' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Original artifact readiness' })).not.toBeInTheDocument()
  })

  it.each([
    ['healthy', 'Healthy'],
    ['degraded', 'Degraded'],
    ['failed', 'Failed'],
  ] as const)('renders %s telemetry classification as text', (classification, label) => {
    renderDashboard(snapshotWith({
      telemetry: { ...systemStatus.telemetry, classification },
    }))

    expect(screen.getByText(label, { selector: '.MuiChip-label' })).toBeVisible()
  })

  it('deduplicates reasons and does not repeat a reason already present in the observation', () => {
    renderDashboard(snapshotWith({
      overall_observation: 'Subscriber lease is missing.',
      telemetry: {
        ...systemStatus.telemetry,
        classification: 'degraded',
        reasons: [
          'Subscriber lease is missing.',
          'Database heartbeat is delayed.',
          'Database heartbeat is delayed.',
        ],
      },
    }))

    expect(screen.getAllByText('Subscriber lease is missing.')).toHaveLength(1)
    expect(screen.getAllByText('Database heartbeat is delayed.')).toHaveLength(1)
  })

  it('keeps overlapping but distinct reason evidence visible', () => {
    renderDashboard(snapshotWith({
      overall_observation: 'Database heartbeat is delayed but still present.',
      telemetry: {
        ...systemStatus.telemetry,
        classification: 'degraded',
        reasons: ['Database heartbeat is delayed.'],
      },
    }))

    expect(screen.getByText('Database heartbeat is delayed but still present.')).toBeVisible()
    expect(screen.getByText('Database heartbeat is delayed.')).toBeVisible()
  })

  it('shows every liveness and readiness state with non-color text labels', () => {
    renderDashboard(snapshotWith({
      services: [
        { name: 'alive-ready', liveness: 'alive', readiness: 'ready', checked_at: systemStatus.checked_at, detail: 'Ready service' },
        { name: 'down-not-ready', liveness: 'not_alive', readiness: 'not_ready', checked_at: systemStatus.checked_at, detail: 'Unavailable service' },
        { name: 'unknown-state', liveness: 'unknown', readiness: 'unknown', checked_at: systemStatus.checked_at, detail: 'Unknown service' },
      ],
    }))

    expect(screen.getByText('Liveness: Alive').closest('.MuiChip-root')).toHaveClass('MuiChip-colorSuccess')
    expect(screen.getByText('Readiness: Ready').closest('.MuiChip-root')).toHaveClass('MuiChip-colorSuccess')
    expect(screen.getByText('Liveness: Not alive').closest('.MuiChip-root')).toHaveClass('MuiChip-colorError')
    expect(screen.getByText('Readiness: Not ready').closest('.MuiChip-root')).toHaveClass('MuiChip-colorWarning')
    expect(screen.getByText('Liveness: Unknown').closest('.MuiChip-root')).toHaveClass('MuiChip-colorDefault')
    expect(screen.getByText('Readiness: Unknown').closest('.MuiChip-root')).toHaveClass('MuiChip-colorDefault')
  })

  it('marks the entire dashboard retained and neutralizes last-known status presentation', () => {
    renderDashboard(snapshotWith(), true)

    expect(screen.getByLabelText('System health retained last known snapshot')).toBeVisible()
    expect(screen.getByText(/Current reachability: Unknown/)).toBeVisible()
    expect(screen.getByText('Last known · Healthy')).toBeVisible()
    expect(within(screen.getByRole('article', { name: 'Last known · Connection state' }))
      .getByText('Unknown')).toBeVisible()
    expect(screen.getByRole('article', { name: 'Last known · Telemetry age' })).toBeVisible()
    expect(screen.getByRole('article', { name: 'Last known · Sensor freshness' })).toBeVisible()
    expect(screen.getAllByText(/Last known ·/, { selector: '.MuiChip-label' }).every((label) =>
      label.closest('.MuiChip-root')?.classList.contains('MuiChip-colorDefault') === true,
    )).toBe(true)
    expect(screen.getByText('Snapshot retained (UTC)')).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Last known service status' })).toBeVisible()
    expect(screen.getByRole('button', { name: /Last known technical details/ })).toBeVisible()
  })

  it('renders an EmptyState for an empty service list', () => {
    renderDashboard(snapshotWith({ services: [] }))

    expect(screen.getByRole('status', { name: 'No service status available' })).toBeVisible()
  })

  it('supports dynamic services and falls back to the API name', () => {
    renderDashboard(snapshotWith({
      services: [{
        name: 'future-edge-worker',
        liveness: 'alive',
        readiness: 'unknown',
        checked_at: systemStatus.checked_at,
        detail: 'A service introduced by a newer backend',
      }],
    }))

    expect(screen.getByRole('heading', { name: 'future-edge-worker' })).toBeVisible()
    expect(screen.getByText('A service introduced by a newer backend')).toBeVisible()
  })

  it('keeps technical evidence collapsed and handles absent diagnostics', () => {
    renderDashboard(snapshotWith({ diagnostics: undefined }))

    const detailsButton = screen.getByRole('button', { name: /Technical details/ })
    expect(detailsButton).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(detailsButton)
    expect(detailsButton).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Diagnostics: Unavailable')).toBeVisible()
    expect(screen.getByText(`Request ID: ${systemStatus.request_id}`)).toBeVisible()
    expect(screen.getByText(/model hash: mock-model-sha256/)).toBeVisible()
  })

  it('shows explicit independent timestamp zones in the evidence strip', () => {
    renderDashboard(snapshotWith())
    const evidence = screen.getByRole('region', { name: 'Snapshot evidence' })

    expect(within(evidence).getByText('Status checked (UTC)')).toBeVisible()
    expect(within(evidence).getByText('Snapshot displayed (UTC)')).toBeVisible()
    expect(within(evidence).getByText('Latest telemetry (Asia/Jakarta, WIB)')).toBeVisible()
    expect(evidence).not.toHaveTextContent('→')
  })

})

describe('formatDuration', () => {
  it.each([
    [null, 'Unknown'],
    [0, '0s'],
    [59.9, '59s'],
    [60, '1m'],
    [90, '1m 30s'],
    [3_720, '1h 2m'],
    [90_000, '1d 1h'],
  ] as const)('formats %s seconds as %s', (seconds, expected) => {
    expect(formatDuration(seconds)).toBe(expected)
  })
})

describe('resolveStatusDisplayMeta', () => {
  it('uses checked-at without inventing a browser timestamp before query data is dated', () => {
    expect(resolveStatusDisplayMeta(systemStatus, 0, false, Date.parse('2026-08-04T10:00:00Z'))).toEqual({
      displayedAt: systemStatus.checked_at,
      pollAgeSeconds: 0,
      retained: false,
    })
  })

  it('computes retained poll age from the query update timestamp', () => {
    expect(resolveStatusDisplayMeta(
      systemStatus,
      Date.parse('2026-08-04T09:58:30Z'),
      true,
      Date.parse('2026-08-04T10:00:00Z'),
    )).toEqual({
      displayedAt: '2026-08-04T09:58:30.000Z',
      pollAgeSeconds: 90,
      retained: true,
    })
  })
})

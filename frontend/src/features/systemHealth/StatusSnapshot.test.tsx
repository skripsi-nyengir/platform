import { ThemeProvider } from '@mui/material/styles'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { SystemStatusResponse } from '../../contracts/systemHealth'
import { systemStatus } from '../../mocks/fixtures/systemHealth'
import { theme } from '../../theme/theme'
import type { StatusDisplayMeta } from './displayMeta'
import { StatusSnapshot } from './StatusSnapshot'

const currentDisplay: StatusDisplayMeta = {
  displayedAt: '2026-08-04T10:00:00.000Z',
  pollAgeSeconds: 0,
  retained: false,
}

const retainedDisplay: StatusDisplayMeta = {
  displayedAt: '2026-08-04T09:58:30.000Z',
  pollAgeSeconds: 90,
  retained: true,
}

function snapshotWith(
  overrides: Partial<SystemStatusResponse> = {},
  telemetryOverrides: Partial<SystemStatusResponse['telemetry']> = {},
): SystemStatusResponse {
  return {
    ...structuredClone(systemStatus),
    ...overrides,
    telemetry: {
      ...structuredClone(systemStatus.telemetry),
      ...telemetryOverrides,
    },
  }
}

function renderCompact(
  snapshot: SystemStatusResponse,
  display: StatusDisplayMeta = currentDisplay,
  onRetry?: () => void,
) {
  return render(
    <ThemeProvider theme={theme} defaultMode="dark" noSsr>
      <StatusSnapshot
        snapshot={snapshot}
        display={display}
        density="compact"
        onRetry={onRetry}
      />
    </ThemeProvider>,
  )
}

describe('StatusSnapshot compact density', () => {
  it('keeps a healthy snapshot concise without observation or technical disclosure', () => {
    renderCompact(snapshotWith())

    expect(screen.getByRole('region', { name: 'Live telemetry health' })).toBeVisible()
    expect(screen.queryByText(systemStatus.overall_observation)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Technical details/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Snapshot evidence' })).not.toBeInTheDocument()
  })

  it.each(['degraded', 'failed'] as const)(
    'shows the operational observation and each unique reason when classification is %s',
    (classification) => {
      const observation = 'Subscriber lease is missing.'
      const uniqueReason = 'Database heartbeat is delayed.'
      renderCompact(snapshotWith(
        { overall_observation: observation },
        {
          classification,
          reasons: [observation, uniqueReason, uniqueReason],
        },
      ))

      expect(screen.getAllByText(observation)).toHaveLength(1)
      expect(screen.getAllByText(uniqueReason)).toHaveLength(1)
    },
  )

  it('marks retained values as last known and neutralizes current reachability', () => {
    renderCompact(snapshotWith(), retainedDisplay)

    expect(screen.getByText('Last known · Healthy').closest('.MuiChip-root'))
      .toHaveClass('MuiChip-colorDefault')
    expect(screen.getByText('Current reachability: Unknown')).toBeVisible()
    expect(screen.getByRole('group', { name: 'Last known live telemetry indicators' })).toBeVisible()
    expect(screen.getByRole('article', { name: 'Last known · Telemetry age' })).toBeVisible()
    expect(screen.getByRole('article', { name: 'Last known · Sensor freshness' })).toBeVisible()

    const connection = screen.getByRole('article', { name: 'Last known · Connection state' })
    expect(within(connection).getByText('Unknown')).toBeVisible()
    expect(within(connection).getByText('Last known: Subscribed')).toBeVisible()
  })

  it('supports Retry activation by pointer and keyboard for a retained snapshot', async () => {
    const user = userEvent.setup()
    const onRetry = vi.fn()
    renderCompact(snapshotWith(), retainedDisplay, onRetry)

    const retry = screen.getByRole('button', { name: 'Retry' })
    await user.click(retry)
    retry.focus()
    await user.keyboard('{Enter}')

    expect(onRetry).toHaveBeenCalledTimes(2)
  })

  it('renders nullable telemetry evidence safely as unknown in compact mode', () => {
    renderCompact(snapshotWith({}, {
      age_seconds: null,
      latest_ts: null,
      last_valid_reading_ts: null,
      database_heartbeat: null,
      fencing_token: null,
      connack_received: null,
      suback_received: null,
      ingress_queue_depth: null,
      dropped_newest_count: null,
      invalid_message_count: null,
      retained_message_count: null,
      active_model_version: null,
      active_scaler_corpus_id: null,
      cursor_ts: null,
      cursor_id: null,
      connection_state: 'unknown',
    }))

    expect(within(screen.getByRole('article', { name: 'Telemetry age' }))
      .getByText('Unknown')).toBeVisible()
    expect(within(screen.getByRole('article', { name: 'Connection state' }))
      .getByText('Unknown')).toBeVisible()
  })
})

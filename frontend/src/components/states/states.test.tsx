import { ThemeProvider } from '@mui/material/styles'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../api/errors'
import type { Availability, Freshness } from '../../contracts/common'
import { theme } from '../../theme/theme'
import { tokens } from '../../theme/tokens'
import { ApiErrorPanel } from './ApiErrorPanel'
import { EmptyState } from './EmptyState'
import { PanelSkeleton } from './PanelSkeleton'
import { PollingFailureNotice } from './PollingFailureNotice'
import { SensorStatus } from './SensorStatus'

function renderWithTheme(ui: ReactNode) {
  return render(<ThemeProvider theme={theme}>{ui}</ThemeProvider>)
}

describe('shared state components', () => {
  it('announces a visible busy skeleton label', () => {
    renderWithTheme(<PanelSkeleton label="Loading telemetry panel" />)

    const status = screen.getByRole('status', { name: 'Loading telemetry panel' })
    expect(status).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByText('Loading telemetry panel')).toBeVisible()
  })

  it('names and describes an empty state with its visible copy', () => {
    renderWithTheme(
      <EmptyState title="No telemetry" detail="Choose a wider time range." />,
    )

    const status = screen.getByRole('status', { name: 'No telemetry' })
    expect(status).toHaveAccessibleDescription('Choose a wider time range.')
    expect(screen.getByText('No telemetry')).toBeVisible()
    expect(screen.getByText('Choose a wider time range.')).toBeVisible()
  })

  it('renders Problem Details, falls back to problem request_id, and retries by keyboard', async () => {
    const user = userEvent.setup()
    const onRetry = vi.fn()
    const error = new ApiError('problem', 'Request rejected', 422, undefined, {
      type: 'https://example.invalid/problems/invalid-time-range',
      title: 'Invalid time range',
      status: 422,
      detail: 'from must be earlier than to',
      instance: '/api/telemetry/history',
      request_id: 'req-problem',
    })

    renderWithTheme(<ApiErrorPanel error={error} onRetry={onRetry} />)

    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('Invalid time range')
    expect(alert).toHaveTextContent('from must be earlier than to')
    expect(alert).toHaveTextContent('Request ID: req-problem')
    screen.getByRole('button', { name: 'Retry' }).focus()
    await user.keyboard('{Enter}')
    expect(onRetry).toHaveBeenCalledOnce()
  })

  it('uses the ApiError request ID and fallback copy when Problem Details is absent', () => {
    const error = new ApiError('network', 'Connection unavailable', undefined, 'req-network')

    renderWithTheme(<ApiErrorPanel error={error} onRetry={vi.fn()} />)

    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('Data request failed')
    expect(alert).toHaveTextContent('Connection unavailable')
    expect(alert).toHaveTextContent('Request ID: req-network')
  })

  it('identifies retained polling data and retries by keyboard', async () => {
    const user = userEvent.setup()
    const onRetry = vi.fn()

    renderWithTheme(
      <PollingFailureNotice
        resource="Latest telemetry"
        lastUpdated="2026-07-19T10:00:00+07:00"
        onRetry={onRetry}
      />,
    )

    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('Latest telemetry')
    expect(alert).toHaveTextContent('2026-07-19T10:00:00+07:00')
    expect(alert).toHaveTextContent(/retained data/i)
    expect(alert).toHaveTextContent(/current data may be outdated or unknown/i)
    screen.getByRole('button', { name: 'Retry' }).focus()
    await user.keyboard(' ')
    expect(onRetry).toHaveBeenCalledOnce()
  })

  const statusCases: readonly {
    availability: Availability
    freshness: Freshness
    label: string
  }[] = [
    { availability: 'unknown', freshness: 'fresh', label: 'Current status unknown' },
    { availability: 'offline', freshness: 'fresh', label: 'Offline sensor' },
    { availability: 'offline', freshness: 'stale', label: 'Offline sensor' },
    { availability: 'online', freshness: 'stale', label: 'Stale telemetry' },
    { availability: 'online', freshness: 'fresh', label: 'Fresh telemetry' },
    {
      availability: 'online',
      freshness: 'unknown',
      label: 'Telemetry freshness unknown',
    },
  ]

  it.each(statusCases)('renders $label as text', ({ availability, freshness, label }) => {
    renderWithTheme(<SensorStatus availability={availability} freshness={freshness} />)

    expect(screen.getByRole('status', { name: label })).toBeVisible()
    expect(screen.getByText(label)).toBeVisible()
  })

  it('supports status-only rendering without telemetry captions', () => {
    const statusOnlyProps = {
      availability: 'online',
      freshness: 'fresh',
      timestamp: '2026-07-19T10:00:00Z',
      ageSeconds: 12,
      statusOnly: true,
    } as const

    renderWithTheme(<SensorStatus {...statusOnlyProps} />)

    expect(screen.getByRole('status', { name: 'Fresh telemetry' })).toBeVisible()
    expect(screen.getByText('Fresh telemetry')).toBeVisible()
    expect(screen.queryByText(/Last telemetry:/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Telemetry age:/)).not.toBeInTheDocument()
  })

  it('shows explicit timestamp and age values or explicit unknown fallbacks', () => {
    const { rerender } = renderWithTheme(
      <SensorStatus
        availability="online"
        freshness="fresh"
        timestamp="2026-07-19T10:00:00Z"
        ageSeconds={12}
      />,
    )

    const technicalCaption = screen.getByText(/Last telemetry: 2026-07-19T10:00:00Z/)
    expect(technicalCaption).toBeVisible()
    expect(screen.getByText(/Telemetry age: 12 seconds/)).toBeVisible()
    expect(technicalCaption).toHaveStyle({
      fontFamily: tokens.font.data,
      fontVariantNumeric: 'tabular-nums',
      overflowWrap: 'anywhere',
    })

    rerender(
      <ThemeProvider theme={theme}>
        <SensorStatus availability="unknown" freshness="unknown" />
      </ThemeProvider>,
    )
    expect(screen.getByText(/Last telemetry timestamp unknown/)).toBeVisible()
    expect(screen.getByText(/Telemetry age unknown/)).toBeVisible()
  })
})

import { CssBaseline } from '@mui/material'
import { ThemeProvider } from '@mui/material/styles'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { AlertEvent, CurrentAlert, CurrentAlertsResponse } from '../contracts/alerts'
import type { AlertStatus } from '../contracts/common'
import { activeDetectedAlert } from '../mocks/fixtures/alerts'
import { fixtureGeneratedAt } from '../mocks/fixtures/telemetry'
import { server } from '../mocks/node'
import { setMockScenario } from '../mocks/state'
import {
  createQueryTestHarness,
  type QueryTestHarness,
} from '../test/queryTestUtils'
import { theme } from '../theme/theme'
import { tokens } from '../theme/tokens'
import { AlertsPage } from './AlertsPage'

const origin = window.location.origin
const from = '2026-07-19T10:00:00Z'
const to = '2026-07-19T11:00:00Z'
const commandTs = '2026-07-19T10:31:00.000Z'

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

function renderAlerts(route = '/alerts') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AlertsPage />
    </MemoryRouter>,
    { wrapper: Providers },
  )
}

function alertForStatus(status: AlertStatus): CurrentAlert {
  const permissions = {
    detected: { can_acknowledge: true, can_resolve: false },
    acknowledged: { can_acknowledge: false, can_resolve: true },
    resolved: { can_acknowledge: false, can_resolve: false },
  }[status]
  return {
    ...activeDetectedAlert,
    status,
    latest_event_ts: status === 'detected' ? activeDetectedAlert.latest_event_ts : commandTs,
    latest_event_id: `event_n4_${status}`,
    ...permissions,
  }
}

function currentAlertsResponse(
  status: AlertStatus,
  page = 1,
  pageSize = 25,
  total = 1,
): CurrentAlertsResponse {
  return {
    request_id: `req-current-${status}`,
    generated_at: fixtureGeneratedAt,
    items: [alertForStatus(status)],
    page,
    page_size: pageSize,
    total,
  }
}

function event(eventType: AlertStatus, eventTs: string): AlertEvent {
  return {
    event_id: `event_n4_${eventType}`,
    alert_id: activeDetectedAlert.alert_id,
    event_ts: eventTs,
    event_type: eventType,
    device_id: 'n4',
    actor: eventType === 'detected' ? 'inference-worker' : 'operator',
    note: null,
    inference_result_window_start_ts: null,
    inference_result_window_end_ts: null,
    inference_model_version: null,
  }
}

function problem(status: number, requestId: string, title = 'Alert action failed') {
  return {
    type: `https://example.invalid/problems/${requestId}`,
    title,
    status,
    detail: status === 409
      ? 'The confirmed alert state changed before this command completed'
      : 'The alert action is temporarily unavailable',
    instance: '/api/alerts/alert_n4_active/acknowledge',
    request_id: requestId,
  }
}

function acknowledgementResponse() {
  return {
    request_id: 'req-acknowledge',
    alert_id: activeDetectedAlert.alert_id,
    status: 'acknowledged',
    event: event('acknowledged', commandTs),
    idempotent_replay: false,
  }
}

beforeEach(() => {
  harness = createQueryTestHarness()
})

afterEach(() => {
  harness.restore()
  vi.restoreAllMocks()
})

describe('AlertsPage', () => {
  it('scopes current and history filters correctly, paginates on the server, and caps page size at 100', async () => {
    const currentRequests: URL[] = []
    const eventRequests: URL[] = []
    server.use(
      http.get(`${origin}/api/alerts/current`, ({ request }) => {
        const url = new URL(request.url)
        currentRequests.push(url)
        const page = Number(url.searchParams.get('page'))
        const pageSize = Number(url.searchParams.get('page_size'))
        return HttpResponse.json(currentAlertsResponse('detected', page, pageSize, 101))
      }),
      http.get(`${origin}/api/alert-events`, ({ request }) => {
        eventRequests.push(new URL(request.url))
        const events = [event('detected', '2026-07-19T10:20:00Z')]
        return HttpResponse.json({
          request_id: 'req-events',
          events,
          next_cursor: null,
          returned_count: events.length,
        })
      }),
    )
    const user = userEvent.setup()
    renderAlerts(`/alerts?sensor=n4&from=${from}&to=${to}`)

    const pageHeading = screen.getByRole('heading', { level: 1, name: 'Alerts' })
    expect(pageHeading).toBeVisible()
    const filterSurface = screen.getByRole('region', { name: 'Alert filters' })
    const filterGroup = within(filterSurface).getByRole('group', { name: 'Alert filters' })
    const sensor = within(filterGroup).getByLabelText('Sensor')
    const status = within(filterGroup).getByLabelText('Status')
    const fromInput = within(filterGroup).getByLabelText('From')
    const toInput = within(filterGroup).getByLabelText('To')
    expect(sensor).toHaveValue('n4')
    expect(status).toHaveValue('')
    expect(fromInput).toHaveValue(from)
    expect(toInput).toHaveValue(to)
    for (const control of [sensor, status, fromInput, toInput]) {
      expect(getComputedStyle(control).fontFamily).toContain('IBM Plex Mono')
      expect(getComputedStyle(control).fontVariantNumeric).toContain('tabular-nums')
    }
    for (const control of [sensor, status, fromInput, toInput]) {
      const label = filterGroup.querySelector(`label[for="${control.id}"]`)
      if (!(label instanceof HTMLLabelElement)) throw new Error(`${control.id} label was not rendered`)
      expect(label).toHaveAttribute('data-shrink', 'true')
      expect(getComputedStyle(label).fontFamily).toContain('Inter')
    }
    expect(filterSurface).toHaveStyle({ marginTop: '24px', padding: '16px' })
    expect(filterGroup).toHaveStyle({
      width: '100%',
      minWidth: '0px',
      flexWrap: 'wrap',
      gap: '8px',
    })
    expect(sensor.closest('.MuiFormControl-root')).toHaveStyle({ minWidth: '136px' })
    expect(status.closest('.MuiFormControl-root')).toHaveStyle({ minWidth: '136px' })
    expect(fromInput.closest('.MuiTextField-root')).toHaveStyle({ minWidth: '220px' })
    expect(toInput.closest('.MuiTextField-root')).toHaveStyle({ minWidth: '220px' })

    const grid = await screen.findByRole('grid', { name: 'Current alerts' })
    const gridRoot = grid.closest('.MuiDataGrid-root')
    if (!(gridRoot instanceof HTMLElement)) throw new Error('Current alerts grid root was not rendered')
    expect(gridRoot).toHaveStyle({
      minWidth: '0px',
      maxWidth: '100%',
      '--DataGrid-headerHeight': '64px',
    })
    expect(within(grid).getAllByRole('columnheader').map((header) => header.textContent)).toEqual([
      'Alert ID',
      'Sensor',
      'Status',
      'Last event',
      'Action',
    ])
    const alertHeader = within(grid).getByRole('columnheader', { name: 'Alert ID' })
    const alertHeaderTitle = alertHeader.querySelector('.MuiDataGrid-columnHeaderTitle')
    if (!(alertHeaderTitle instanceof HTMLElement)) throw new Error('Alert ID header title was not rendered')
    expect(alertHeaderTitle).toHaveStyle({
      lineHeight: '1.15',
      overflow: 'visible',
      textOverflow: 'clip',
      whiteSpace: 'normal',
    })
    const alertCell = within(grid).getByRole('gridcell', { name: activeDetectedAlert.alert_id })
    expect(alertCell).toHaveStyle({
      fontFamily: tokens.font.data,
      fontVariantNumeric: 'tabular-nums',
      overflowWrap: 'anywhere',
      whiteSpace: 'normal',
    })
    expect(getComputedStyle(within(grid).getByRole('gridcell', { name: 'Active' })).fontFamily)
      .toContain('Inter')
    const actionRow = within(grid).getByRole('button', { name: 'Acknowledge alert' }).parentElement
    if (!(actionRow instanceof HTMLElement)) throw new Error('Alert actions have no row')
    expect(actionRow).toHaveStyle({ flexWrap: 'wrap', gap: '4px' })

    await waitFor(() => expect(currentRequests).not.toHaveLength(0))
    const firstCurrent = currentRequests.at(-1)
    if (firstCurrent === undefined) throw new Error('Expected a current-alert request')
    expect(Object.fromEntries(firstCurrent.searchParams)).toEqual({
      device_id: 'n4',
      page: '1',
      page_size: '25',
    })
    await waitFor(() => expect(eventRequests).not.toHaveLength(0))
    const firstEvents = eventRequests.at(-1)
    if (firstEvents === undefined) throw new Error('Expected an alert-events request')
    expect(firstEvents.searchParams.get('device_id')).toBe('n4')
    expect(firstEvents.searchParams.get('from')).toBe(from)
    expect(firstEvents.searchParams.get('to')).toBe(to)
    expect(firstEvents.searchParams.has('status')).toBe(false)
    expect(firstEvents.searchParams.has('page')).toBe(false)

    await user.click(screen.getByRole('button', { name: 'Go to next page' }))
    await waitFor(() => expect(currentRequests.some((url) => url.searchParams.get('page') === '2')).toBe(true))

    const pageSizeControl = screen.getByRole('combobox', {
      name: /Rows per page/i,
      hidden: true,
    })
    fireEvent.mouseDown(pageSizeControl)
    const listbox = await screen.findByRole('listbox')
    const options = within(listbox).getAllByRole('option')
    expect(options.map((option) => option.textContent)).toEqual(['10', '25', '50', '100'])
    await user.click(within(listbox).getByRole('option', { name: '100' }))
    await waitFor(() => expect(currentRequests.some((url) =>
      url.searchParams.get('page') === '1' && url.searchParams.get('page_size') === '100',
    )).toBe(true))
  })

  it('opens the selected alert history from a keyboard-selected row', async () => {
    setMockScenario('active-anomaly')
    renderAlerts(`/alerts?from=${from}&to=${to}`)
    const grid = await screen.findByRole('grid', { name: 'Current alerts' })
    const alertCell = await within(grid).findByRole('gridcell', { name: activeDetectedAlert.alert_id })
    const user = userEvent.setup()

    alertCell.focus()
    await user.keyboard(' ')

    await waitFor(() => expect(harness.queryClient.getQueryCache().find({
      queryKey: ['alerts', 'events', activeDetectedAlert.alert_id, null, from, to, 200, null],
      exact: true,
    })).toBeDefined())
    expect(screen.getByRole('region', { name: 'Immutable alert event history' })).toHaveTextContent(
      activeDetectedAlert.alert_id,
    )
  })

  it('activates lifecycle actions from the keyboard without selecting the row', async () => {
    setMockScenario('active-anomaly')
    const requestBodies: string[] = []
    server.use(
      http.post(`${origin}/api/alerts/:alertId/acknowledge`, async ({ request }) => {
        requestBodies.push(await request.text())
        return HttpResponse.json(acknowledgementResponse())
      }),
    )
    const user = userEvent.setup()
    renderAlerts()
    const acknowledge = await screen.findByRole('button', { name: 'Acknowledge alert' })

    acknowledge.focus()
    await user.keyboard('{Enter}')

    await waitFor(() => expect(requestBodies).toHaveLength(1))
    expect(harness.queryClient.getQueryCache().find({
      queryKey: ['alerts', 'events', activeDetectedAlert.alert_id, null, null, null, 200, null],
      exact: true,
    })).toBeUndefined()
  })

  it('renders immutable event history in the server-provided order', async () => {
    const events = [
      event('detected', '2026-07-19T10:20:00Z'),
      event('acknowledged', '2026-07-19T10:31:00Z'),
      event('resolved', '2026-07-19T10:40:00Z'),
    ]
    server.use(
      http.get(`${origin}/api/alert-events`, () => HttpResponse.json({
        request_id: 'req-ordered-events',
        events,
        next_cursor: null,
        returned_count: events.length,
      })),
    )
    renderAlerts(`/alerts?from=${from}&to=${to}`)

    const history = await screen.findByRole('region', { name: 'Immutable alert event history' })
    const items = await within(history).findAllByRole('listitem')
    expect(items.map((item) => item.textContent)).toEqual([
      expect.stringContaining('2026-07-19T10:20:00Z'),
      expect.stringContaining('2026-07-19T10:31:00Z'),
      expect.stringContaining('2026-07-19T10:40:00Z'),
    ])
    const firstEvent = within(items[0])
    const alertIdValue = firstEvent.getByText(activeDetectedAlert.alert_id)
    for (const technicalValue of [
      firstEvent.getByText('2026-07-19T10:20:00Z'),
      alertIdValue,
      firstEvent.getByText('n4'),
      firstEvent.getByText('inference-worker'),
    ]) {
      expect(technicalValue).toHaveStyle({
        fontFamily: tokens.font.data,
        fontVariantNumeric: 'tabular-nums',
        overflowWrap: 'anywhere',
      })
    }
    expect(getComputedStyle(firstEvent.getByRole('heading', { level: 3, name: 'Detected' })).fontFamily)
      .toContain('Inter')
    const metadataLine = alertIdValue.parentElement
    if (metadataLine === null) throw new Error('Alert event metadata has no label line')
    expect(getComputedStyle(metadataLine).fontFamily).toContain('Inter')
    expect(within(history).queryByRole('button')).not.toBeInTheDocument()
  })

  it.each([
    ['detected', 'Acknowledge alert', 'Resolve alert'],
    ['acknowledged', 'Resolve alert', 'Acknowledge alert'],
    ['resolved', undefined, 'Acknowledge alert'],
  ] satisfies ReadonlyArray<readonly [AlertStatus, string | undefined, string]>) (
    'shows only the lifecycle action permitted for %s alerts',
    async (status, includedAction, excludedAction) => {
      server.use(
        http.get(`${origin}/api/alerts/current`, () =>
          HttpResponse.json(currentAlertsResponse(status)),
        ),
      )
      renderAlerts()
      await screen.findByRole('grid', { name: 'Current alerts' })

      if (includedAction === undefined) {
        expect(screen.queryByRole('button', { name: /alert$/i })).not.toBeInTheDocument()
      } else {
        expect(await screen.findByRole('button', { name: includedAction })).toBeEnabled()
      }
      expect(screen.queryByRole('button', { name: excludedAction })).not.toBeInTheDocument()
      if (status === 'resolved') {
        expect(screen.queryByRole('button', { name: 'Resolve alert' })).not.toBeInTheDocument()
      }
    },
  )

  it('keeps confirmed state while pending and retries the exact saved mutation variables', async () => {
    setMockScenario('active-anomaly')
    const requestBodies: string[] = []
    let attempt = 0
    let releaseResponse: () => void = () => {
      throw new Error('Response gate was not initialized')
    }
    const responseGate = new Promise<void>((resolve) => {
      releaseResponse = resolve
    })
    server.use(
      http.post(`${origin}/api/alerts/:alertId/acknowledge`, async ({ request }) => {
        requestBodies.push(await request.text())
        attempt += 1
        if (attempt === 1) {
          await responseGate
          return HttpResponse.json(problem(503, 'req-action-failed'), { status: 503 })
        }
        return HttpResponse.json(acknowledgementResponse())
      }),
    )
    const uuid = vi.spyOn(crypto, 'randomUUID').mockReturnValue('550e8400-e29b-41d4-a716-446655440000')
    const timestamp = vi.spyOn(Date.prototype, 'toISOString').mockReturnValue(commandTs)
    const user = userEvent.setup()
    renderAlerts()
    const acknowledge = await screen.findByRole('button', { name: 'Acknowledge alert' })

    await user.click(acknowledge)
    await waitFor(() => expect(acknowledge).toBeDisabled())
    expect(screen.getByRole('grid', { name: 'Current alerts' })).toHaveTextContent('Active')
    expect(screen.queryByRole('button', { name: 'Resolve alert' })).not.toBeInTheDocument()
    expect(requestBodies).toHaveLength(1)

    releaseResponse()
    const retry = await screen.findByRole('button', { name: 'Retry action' })
    await user.click(retry)
    await waitFor(() => expect(requestBodies).toHaveLength(2))

    expect(requestBodies[1]).toBe(requestBodies[0])
    expect(JSON.parse(requestBodies[0])).toEqual({
      command_id: '550e8400-e29b-41d4-a716-446655440000',
      event_ts: commandTs,
    })
    expect(uuid).toHaveBeenCalledOnce()
    expect(timestamp).toHaveBeenCalledOnce()
  })

  it('explains a 409 conflict and refreshes the confirmed current state', async () => {
    let status: AlertStatus = 'detected'
    let currentRequestCount = 0
    server.use(
      http.get(`${origin}/api/alerts/current`, () => {
        currentRequestCount += 1
        return HttpResponse.json(currentAlertsResponse(status))
      }),
      http.post(`${origin}/api/alerts/:alertId/acknowledge`, () => {
        status = 'acknowledged'
        return HttpResponse.json(problem(409, 'req-lifecycle-conflict', 'Lifecycle conflict'), {
          status: 409,
        })
      }),
    )
    const user = userEvent.setup()
    renderAlerts()

    await user.click(await screen.findByRole('button', { name: 'Acknowledge alert' }))

    expect(await screen.findByText(/Lifecycle conflict \(409\)/)).toBeVisible()
    expect(screen.getByText(/confirmed current state was refreshed/i)).toBeVisible()
    await waitFor(() => expect(currentRequestCount).toBeGreaterThan(1))
    expect(await screen.findByRole('button', { name: 'Resolve alert' })).toBeEnabled()
    expect(screen.queryByRole('button', { name: 'Retry action' })).not.toBeInTheDocument()
  })
})

import { CssBaseline } from '@mui/material'
import { ThemeProvider } from '@mui/material/styles'
import type { LineChartProps } from '@mui/x-charts/LineChart'
import { HttpResponse, http } from 'msw'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { InferenceResultsResponse } from '../contracts/inference'
import type { TelemetryHistoryResponse } from '../contracts/telemetry'
import { server } from '../mocks/node'
import { setMockScenario } from '../mocks/state'
import {
  createQueryTestHarness,
  type QueryTestHarness,
} from '../test/queryTestUtils'
import { theme } from '../theme/theme'
import { tokens } from '../theme/tokens'
import { SensorDetailPage } from './SensorDetailPage'

const lineChartSpy = vi.hoisted(() => vi.fn())

vi.mock('@mui/x-charts/LineChart', () => ({
  LineChart: (props: LineChartProps) => {
    lineChartSpy(props)
    return null
  },
}))

const origin = window.location.origin
const from = '2026-07-19T10:00:00Z'
const to = '2026-07-19T10:30:00Z'

let harness: QueryTestHarness

function LocationProbe() {
  const location = useLocation()
  return <output data-testid="location">{location.pathname}{location.search}</output>
}

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

function renderSensor(route: string) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path="/" element={<h1>Overview</h1>} />
        <Route path="/sensors/:sensorId" element={<SensorDetailPage />} />
      </Routes>
      <LocationProbe />
    </MemoryRouter>,
    { wrapper: Providers },
  )
}

function currentLocation(): URL {
  const value = screen.getByTestId('location').textContent
  if (value === null) throw new Error('Location probe has no value')
  return new URL(value, origin)
}

function problem(requestId: string, instance: string) {
  return {
    type: `https://example.invalid/problems/${requestId}`,
    title: 'Sensor history request failed',
    status: 503,
    detail: 'The selected sensor resource is temporarily unavailable',
    instance,
    request_id: requestId,
  }
}

beforeEach(() => {
  harness = createQueryTestHarness()
  lineChartSpy.mockClear()
})

afterEach(() => {
  harness.restore()
})

describe('SensorDetailPage', () => {
  it('uses the route sensor, restores URL controls, preserves filters, and never polls history', async () => {
    setMockScenario('active-anomaly')
    const user = userEvent.setup()
    renderSensor(
      `/sensors/n4?sensor=n2&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&bucket=5m&model_version=model-v7&__scenario=active-anomaly`,
    )

    expect(screen.getByRole('heading', { level: 1, name: 'Sensor Detail & History' })).toBeVisible()
    const selectedSensorLine = screen.getByText((_, element) =>
      element?.tagName === 'P' && element.textContent === 'Selected sensor: n4',
    )
    expect(selectedSensorLine).toBeVisible()
    expect(screen.getByRole('combobox', { name: 'Sensor' })).toHaveValue('n4')
    expect(screen.getByRole('textbox', { name: 'From' })).toHaveValue(from)
    expect(screen.getByRole('textbox', { name: 'To' })).toHaveValue(to)
    expect(screen.getByRole('combobox', { name: 'Bucket' })).toHaveValue('5m')
    expect(await screen.findByRole('status', { name: 'Fresh telemetry' })).toBeVisible()
    const temperatureChartImage = await screen.findByRole('img', { name: 'Temperature chart for sensor n4' })
    const humidityChartImage = screen.getByRole('img', { name: 'Relative humidity chart for sensor n4' })
    const scoreChartImage = screen.getByRole('img', { name: 'Anomaly score and threshold chart for sensor n4' })
    expect(temperatureChartImage).toBeVisible()
    expect(humidityChartImage).toBeVisible()
    expect(scoreChartImage).toBeVisible()
    const chartGroup = screen.getByRole('group', { name: 'Temporal charts for sensor n4' })
    expect(chartGroup).toHaveStyle({ display: 'grid', gap: '8px', minWidth: '0px' })
    expect(chartGroup.style.gridTemplateRows).toBe('')
    expect(chartGroup.style.height).toBe('')
    expect(chartGroup.style.overflow).toBe('')

    const charts = lineChartSpy.mock.calls.map(([props]) => props as LineChartProps)
    const temperatureChart = charts.find(
      (props) => props.id === 'temperature-chart-n4',
    )
    if (temperatureChart === undefined) throw new Error('Temperature chart was not rendered')
    expect(temperatureChart).toMatchObject({
      id: 'temperature-chart-n4',
      title: 'Temperature',
      desc: expect.stringContaining('Temperature in degrees Celsius.'),
      height: tokens.size.control * 7,
      hideLegend: true,
      skipAnimation: true,
      xAxis: [{
        id: 'temperature-x-axis',
        label: 'Date',
        scaleType: 'time',
        min: new Date(from),
        max: new Date(to),
      }],
      yAxis: [{ id: 'temperature-y-axis', label: 'Temperature (°C)' }],
      series: [{
        id: 'temperature-series',
        color: theme.palette.primary.main,
        connectNulls: false,
        curve: 'linear',
        showMark: false,
      }],
    })
    expect(temperatureChartImage).toHaveAttribute('aria-description', temperatureChart.desc)
    expect(temperatureChart?.xAxis?.[0]).not.toHaveProperty('zoom')
    expect(temperatureChart).not.toHaveProperty('showToolbar', true)
    expect(temperatureChart.xAxis?.[0]?.data).toSatisfy(
      (points: readonly unknown[]) => points.every((point) => point instanceof Date),
    )

    const humidityChart = charts.find(
      (props) => props.id === 'humidity-chart-n4',
    )
    if (humidityChart === undefined) throw new Error('Relative humidity chart was not rendered')
    expect(humidityChart).toMatchObject({
      id: 'humidity-chart-n4',
      title: 'Relative humidity',
      desc: expect.stringContaining('Relative humidity in percent.'),
      height: tokens.size.control * 7,
      hideLegend: true,
      skipAnimation: true,
      xAxis: [{
        id: 'humidity-x-axis',
        label: 'Date',
        scaleType: 'time',
        min: new Date(from),
        max: new Date(to),
      }],
      yAxis: [{ id: 'humidity-y-axis', label: 'Relative humidity (%)' }],
      series: [{
        id: 'humidity-series',
        color: theme.palette.success.main,
        connectNulls: false,
        curve: 'linear',
        showMark: false,
      }],
    })
    expect(humidityChartImage).toHaveAttribute('aria-description', humidityChart.desc)

    const scoreChart = charts.find(
      (props) => props.id === 'score-chart-n4',
    )
    if (scoreChart === undefined) throw new Error('Anomaly score chart was not rendered')
    expect(scoreChart).toMatchObject({
      id: 'score-chart-n4',
      title: 'Anomaly score and threshold',
      desc: expect.stringContaining('Diamond marks identify anomalous window ends.'),
      height: tokens.size.control * 7,
      skipAnimation: true,
      xAxis: [{
        id: 'score-x-axis',
        label: 'Date',
        scaleType: 'time',
        min: new Date(from),
        max: new Date(to),
      }],
      yAxis: [{ id: 'score-y-axis', label: 'Score' }],
      series: [
        { id: 'score-series', color: theme.palette.warning.main, showMark: false },
        { id: 'threshold-series', color: theme.palette.text.secondary, showMark: false },
        { id: 'anomaly-series', color: theme.palette.error.main, shape: 'diamond', showMark: true },
      ],
    })
     expect(scoreChartImage).toHaveAttribute('aria-description', scoreChart.desc)
     for (const chart of [temperatureChart, humidityChart, scoreChart]) {
       expect(chart).toHaveProperty('disableKeyboardNavigation', true)
       expect(chart).not.toHaveProperty('role')
       expect(chart).not.toHaveProperty('aria-label')
     }
    expect(scoreChart.series[1]?.data).toEqual(
      scoreChart.series[0]?.data?.map(() => 0.8),
    )
    const filters = screen.getByRole('group', { name: 'Temporal filters' })
    expect(filters).toHaveStyle({ marginTop: '24px' })

    const selectedSensorValue = within(selectedSensorLine).getByText('n4')
    expect(getComputedStyle(selectedSensorLine).fontFamily).toContain('Inter')
    expect(selectedSensorValue).toHaveStyle({
      fontFamily: tokens.font.data,
      fontVariantNumeric: 'tabular-nums',
      overflowWrap: 'anywhere',
    })

    const snapshot = await screen.findByRole('region', { name: 'Sensor n4 snapshot' })
    expect(snapshot).toHaveStyle({ minWidth: '0px', padding: '16px' })
    const snapshotView = within(snapshot)
    const temperature = snapshotView.getByText('25.9 °C')
    const humidity = snapshotView.getByText('63.9 %')
    for (const measurement of [temperature, humidity]) {
      expect(measurement).toHaveStyle({
        fontFamily: tokens.font.data,
        fontVariantNumeric: 'tabular-nums',
        overflowWrap: 'anywhere',
      })
      const measurementLine = measurement.parentElement
      if (measurementLine === null) throw new Error('Snapshot measurement has no label line')
      expect(getComputedStyle(measurementLine).fontFamily).toContain('Inter')
    }
    const measurementRow = temperature.parentElement?.parentElement
    if (!(measurementRow instanceof HTMLElement)) throw new Error('Snapshot measurements have no row')
    expect(measurementRow).toHaveStyle({ minWidth: '0px', flexWrap: 'wrap', gap: '12px' })

    const telemetrySummary = screen.getByRole('region', { name: 'Telemetry history' })
    const inferenceSummary = screen.getByRole('region', { name: 'Inference history' })
    expect(telemetrySummary).toHaveStyle({ minWidth: '0px', padding: '16px' })
    expect(inferenceSummary).toHaveStyle({ minWidth: '0px', padding: '16px' })
    expect(within(telemetrySummary).getByText('6 bounded telemetry records')).toHaveStyle({
      fontFamily: tokens.font.data,
      fontVariantNumeric: 'tabular-nums',
      overflowWrap: 'anywhere',
    })
    expect(within(inferenceSummary).getByText('4 bounded inference records')).toHaveStyle({
      fontFamily: tokens.font.data,
      fontVariantNumeric: 'tabular-nums',
      overflowWrap: 'anywhere',
    })
    expect(telemetrySummary.parentElement).toHaveStyle({
      gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
      gap: '8px',
    })

    const relatedHistory = await screen.findByRole('region', { name: 'Related alert history' })
    expect(relatedHistory).toHaveTextContent('Detected')
    const relatedCard = relatedHistory.querySelector('article')
    if (!(relatedCard instanceof HTMLElement)) throw new Error('Related alert card was not rendered')
    expect(relatedCard.parentElement).toHaveStyle({
      gridTemplateColumns: 'repeat(auto-fit, minmax(min(320px, 100%), 1fr))',
    })
    expect(relatedCard).toHaveStyle({ minWidth: '0px', padding: '16px' })
    const relatedCardView = within(relatedCard)
    for (const eventValue of [
      relatedCardView.getByText('2026-07-19T10:20:00Z'),
      relatedCardView.getByText('alert_n4_active'),
      relatedCardView.getByText('inference-worker'),
      relatedCardView.getByText('2026-07-19T10:15:00Z – 2026-07-19T10:20:00Z'),
    ]) {
      expect(eventValue).toHaveStyle({
        fontFamily: tokens.font.data,
        fontVariantNumeric: 'tabular-nums',
        overflowWrap: 'anywhere',
      })
      const eventLine = eventValue.parentElement
      if (eventLine === null) throw new Error('Related alert value has no label line')
      expect(getComputedStyle(eventLine).fontFamily).toContain('Inter')
    }

    const telemetryKey = ['telemetry', 'history', 'n4', from, to, '5m', 2_000, null] as const
    const inferenceKey = ['inference', 'results', 'n4', from, to, '5m', 2_000, null, 'model-v7'] as const
    const alertKey = ['alerts', 'events', null, 'n4', from, to, 200, null] as const
    await waitFor(() => expect(harness.queryClient.getQueryData(telemetryKey)).toBeDefined())
    expect(harness.queryClient.getQueryCache().find({ queryKey: telemetryKey, exact: true })?.options)
      .not.toHaveProperty('refetchInterval')
    expect(harness.queryClient.getQueryCache().find({ queryKey: inferenceKey, exact: true })?.options)
      .not.toHaveProperty('refetchInterval')
    expect(harness.queryClient.getQueryCache().find({ queryKey: alertKey, exact: true })?.options)
      .not.toHaveProperty('refetchInterval')

    await user.selectOptions(screen.getByRole('combobox', { name: 'Sensor' }), 'n3')
    await waitFor(() => expect(currentLocation().pathname).toBe('/sensors/n3'))
    const location = currentLocation()
    expect(location.searchParams.get('sensor')).toBe('n3')
    expect(location.searchParams.get('from')).toBe(from)
    expect(location.searchParams.get('to')).toBe(to)
    expect(location.searchParams.get('bucket')).toBe('5m')
    expect(location.searchParams.get('model_version')).toBe('model-v7')
    expect(location.searchParams.get('__scenario')).toBe('active-anomaly')
    await waitFor(() => expect(screen.getByText((_, element) =>
      element?.tagName === 'P' && element.textContent === 'Selected sensor: n3',
    )).toBeVisible())
  })

  it('redirects an invalid route sensor to Overview', async () => {
    renderSensor('/sensors/n7?sensor=n4')

    expect(await screen.findByRole('heading', { level: 1, name: 'Overview' })).toBeVisible()
    expect(currentLocation().pathname).toBe('/')
    expect(screen.queryByRole('heading', { name: 'Sensor Detail & History' })).not.toBeInTheDocument()
  })

  it('preserves gap records in the chart and exposes the same bounded telemetry and inference rows', async () => {
    setMockScenario('data-gap')
    const user = userEvent.setup()
    renderSensor(`/sensors/n5?sensor=n5&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&bucket=5m`)

    await screen.findByRole('img', { name: 'Temperature chart for sensor n5' })
    const temperatureChart = lineChartSpy.mock.calls
      .map(([props]) => props as LineChartProps)
      .find((props) => props.id === 'temperature-chart-n5')
    expect(temperatureChart?.series[0]?.data).toContain(null)
    expect(temperatureChart?.series[0]).toMatchObject({ connectNulls: false })

    const telemetryKey = ['telemetry', 'history', 'n5', from, to, '5m', 2_000, null] as const
    const inferenceKey = ['inference', 'results', 'n5', from, to, '5m', 2_000, null, null] as const
    const telemetry = harness.queryClient.getQueryData<TelemetryHistoryResponse>(telemetryKey)
    const inference = harness.queryClient.getQueryData<InferenceResultsResponse>(inferenceKey)
    expect(telemetry?.points.some((point) => point.gap_before)).toBe(true)
    expect(telemetry?.returned_count).toBe(5)
    expect(inference?.returned_count).toBe(4)

    await user.click(screen.getByRole('button', { name: 'Lihat data' }))
    const dialog = screen.getByRole('dialog', { name: 'History data for n5' })
    expect(dialog).toHaveTextContent('9 bounded records returned')
    expect(within(dialog).getAllByRole('gridcell', { name: 'Telemetry' })).toHaveLength(5)
    expect(within(dialog).getAllByRole('gridcell', { name: 'Inference' })).toHaveLength(4)
    expect(within(dialog).getByRole('gridcell', { name: 'Yes' })).toBeVisible()
    const inferenceWindowCell = within(dialog).getByRole('gridcell', {
      name: '2026-07-19T10:15:00Z – 2026-07-19T10:20:00Z',
    })
    expect(inferenceWindowCell).toBeVisible()
    expect(inferenceWindowCell).toHaveStyle({
      fontFamily: tokens.font.data,
      fontVariantNumeric: 'tabular-nums',
      whiteSpace: 'normal',
    })
  })

  it('uses raw bounds without polling while preserving the history composition', async () => {
    setMockScenario('active-anomaly')
    renderSensor(`/sensors/n4?sensor=n4&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&bucket=raw`)

    const chartGroup = await screen.findByRole('group', { name: 'Temporal charts for sensor n4' })
    expect(chartGroup).toHaveStyle({ display: 'grid', gap: '8px', minWidth: '0px' })
    expect(chartGroup.style.gridTemplateRows).toBe('')
    expect(chartGroup.style.height).toBe('')
    expect(chartGroup.style.overflow).toBe('')
    const telemetryKey = ['telemetry', 'history', 'n4', from, to, 'raw', 5_000, null] as const
    const inferenceKey = ['inference', 'results', 'n4', from, to, 'raw', 5_000, null, null] as const
    await waitFor(() => expect(harness.queryClient.getQueryData(telemetryKey)).toBeDefined())
    expect(harness.queryClient.getQueryData(inferenceKey)).toBeDefined()
    expect(harness.queryClient.getQueryCache().find({ queryKey: telemetryKey, exact: true })?.options)
      .not.toHaveProperty('refetchInterval')
    expect(harness.queryClient.getQueryCache().find({ queryKey: inferenceKey, exact: true })?.options)
      .not.toHaveProperty('refetchInterval')
  })

  it('keeps inference, chart, and bounded dialog available when telemetry is empty', async () => {
    setMockScenario('active-anomaly')
    server.use(
      http.get(`${origin}/api/telemetry/history`, ({ request }) => {
        const url = new URL(request.url)
        return HttpResponse.json({
          request_id: 'req_empty_telemetry_history',
          device_id: 'n4',
          from: url.searchParams.get('from'),
          to: url.searchParams.get('to'),
          bucket: url.searchParams.get('bucket'),
          points: [],
          next_cursor: null,
          returned_count: 0,
        })
      }),
    )
    const user = userEvent.setup()
    renderSensor(`/sensors/n4?sensor=n4&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&bucket=5m`)

    expect(await screen.findByRole('status', { name: 'No telemetry history' })).toBeVisible()
    expect(await screen.findByText('4 bounded inference records')).toBeVisible()
    expect(screen.getByRole('img', { name: 'Anomaly score and threshold chart for sensor n4' })).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Lihat data' }))

    const dialog = screen.getByRole('dialog', { name: 'History data for n4' })
    expect(dialog).toHaveTextContent('4 bounded records returned')
    expect(within(dialog).queryByRole('gridcell', { name: 'Telemetry' })).not.toBeInTheDocument()
    expect(within(dialog).getAllByRole('gridcell', { name: 'Inference' })).toHaveLength(4)
  })

  it.each([
    {
      name: 'telemetry',
      path: '/api/telemetry/history',
      requestId: 'req_telemetry_panel',
      failedRegion: 'Telemetry history',
      visibleText: '4 bounded inference records',
    },
    {
      name: 'inference',
      path: '/api/inference-results',
      requestId: 'req_inference_panel',
      failedRegion: 'Inference history',
      visibleText: '6 bounded telemetry records',
    },
    {
      name: 'alert history',
      path: '/api/alert-events',
      requestId: 'req_alert_history_panel',
      failedRegion: 'Related alert history',
      visibleText: '6 bounded telemetry records',
    },
  ])('keeps sibling panels visible when $name fails', async ({
    path,
    requestId,
    failedRegion,
    visibleText,
  }) => {
    setMockScenario('active-anomaly')
    server.use(
      http.get(`${origin}${path}`, () =>
        HttpResponse.json(problem(requestId, path), { status: 503 }),
      ),
    )
    renderSensor(`/sensors/n4?sensor=n4&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&bucket=5m`)

    const failedPanel = screen.getByRole('region', { name: failedRegion })
    expect(await within(failedPanel).findByRole('alert')).toHaveTextContent(requestId)
    expect(await within(failedPanel).findByRole('button', { name: 'Retry' })).toBeEnabled()
    expect(await screen.findByText(visibleText)).toBeVisible()
    expect(screen.getByRole('img', { name: 'Anomaly score and threshold chart for sensor n4' })).toBeVisible()

    if (failedRegion === 'Related alert history') {
      expect(screen.getByRole('region', { name: 'Telemetry history' })).toBeVisible()
      expect(screen.getByRole('region', { name: 'Inference history' })).toBeVisible()
    } else {
      expect(await screen.findByRole('region', { name: 'Related alert history' })).toHaveTextContent('Detected')
    }
  })

  it('shows independent empty states without hiding restored filters', async () => {
    setMockScenario('empty')
    renderSensor(`/sensors/n6?sensor=n6&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&bucket=5m`)

    expect(await screen.findByRole('status', { name: 'No telemetry history' })).toBeVisible()
    expect(screen.getByRole('status', { name: 'No inference history' })).toBeVisible()
    expect(screen.getByRole('status', { name: 'No related alert history' })).toBeVisible()
    expect(screen.getByRole('group', { name: 'Temporal filters' })).toBeVisible()
    expect(screen.queryByRole('group', { name: 'Temporal charts for sensor n6' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Lihat data' })).not.toBeInTheDocument()
  })
})

import { CssBaseline } from '@mui/material'
import { ThemeProvider } from '@mui/material/styles'
import type { BarChartProps } from '@mui/x-charts/BarChart'
import type { LineChartProps } from '@mui/x-charts/LineChart'
import type { ScatterChartProps, ScatterMarkerProps } from '@mui/x-charts/ScatterChart'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { server } from '../mocks/node'
import { setMockScenario } from '../mocks/state'
import {
  createQueryTestHarness,
  type QueryTestHarness,
} from '../test/queryTestUtils'
import { theme } from '../theme/theme'
import { tokens } from '../theme/tokens'
import { EdaPage } from './EdaPage'

const lineChartSpy = vi.hoisted(() => vi.fn())
const barChartSpy = vi.hoisted(() => vi.fn())
const scatterChartSpy = vi.hoisted(() => vi.fn())

vi.mock('@mui/x-charts/BarChart', () => ({
  BarChart: (props: BarChartProps) => {
    barChartSpy(props)
    return <div data-chart-id={props.id} />
  },
}))

vi.mock('@mui/x-charts/LineChart', () => ({
  LineChart: (props: LineChartProps) => {
    lineChartSpy(props)
    return <div data-chart-id={props.id} />
  },
}))

vi.mock('@mui/x-charts/ScatterChart', () => ({
  ScatterChart: (props: ScatterChartProps) => {
    scatterChartSpy(props)
    return <div data-chart-id={props.id} />
  },
  ScatterMarker: ({ x, y, color, size, isHighlighted, isFaded }: ScatterMarkerProps) => (
    <circle
      cx={x}
      cy={y}
      fill={color}
      opacity={isFaded ? 0.3 : 1}
      r={(isHighlighted ? 1.2 : 1) * size}
    />
  ),
}))

const origin = window.location.origin
const from = '2026-07-19T10:00:00Z'
const to = '2026-07-19T10:30:00Z'
const panelNames = [
  'Quality and coverage',
  'Missingness',
  'Distributions',
  'Temporal patterns',
  'Correlation and scatter',
  'Sensor comparison',
  'Candidate outliers',
] as const

let harness: QueryTestHarness

function LocationProbe() {
  const location = useLocation()
  return <output data-testid="location-search">{location.search}</output>
}

function Providers({ children, route }: { children: ReactNode; route: string }) {
  const QueryProvider = harness.wrapper
  return (
    <QueryProvider>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route path="/eda" element={<>{children}<LocationProbe /></>} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    </QueryProvider>
  )
}

function renderEda(route = `/eda?from=${from}&to=${to}&bucket=5m`) {
  return render(<EdaPage />, {
    wrapper: ({ children }) => <Providers route={route}>{children}</Providers>,
  })
}

function problem(requestId: string) {
  return {
    type: `https://example.invalid/problems/${requestId}`,
    title: 'EDA request failed',
    status: 503,
    detail: 'The requested EDA evidence is temporarily unavailable',
    instance: '/api/eda/test',
    request_id: requestId,
  }
}

function elementWithText(container: HTMLElement, text: string): HTMLElement {
  const matches = [...container.querySelectorAll<HTMLElement>('*')]
    .filter((element) => element.textContent === text)
  const element = matches.find((match) => (
    ![...match.children].some((child) => child.textContent === text)
  ))
  if (element === undefined) throw new Error(`Missing element: ${text}`)
  return element
}

beforeEach(() => {
  harness = createQueryTestHarness()
  barChartSpy.mockClear()
  lineChartSpy.mockClear()
  scatterChartSpy.mockClear()
})

afterEach(() => {
  harness.restore()
})

describe('EdaPage examiner-facing exploration', () => {
  it('renders the seven named bounded panels and all six comparison sensors without mutation actions', async () => {
    renderEda()

    expect(screen.getByRole('heading', { level: 1, name: 'EDA' })).toBeVisible()
    for (const name of panelNames) {
      expect(screen.getByRole('heading', { level: 2, name })).toBeVisible()
    }
    expect(screen.getByRole('combobox', { name: 'Sensor' })).toHaveValue('')
    expect(screen.getByRole('textbox', { name: 'From' })).toHaveValue(from)
    expect(screen.getByRole('textbox', { name: 'To' })).toHaveValue(to)
    expect(screen.getByRole('combobox', { name: 'Bucket' })).toHaveValue('5m')
    const sampleSize = screen.getByRole('spinbutton', { name: 'Sample size' })
    expect(sampleSize).toHaveValue(1_000)
    expect(sampleSize.closest('.MuiTextField-root')).toHaveStyle({ minWidth: '160px' })
    expect(screen.getByRole('combobox', { name: 'X field' })).toHaveValue('temperature_c')
    expect(screen.getByRole('combobox', { name: 'Y field' })).toHaveValue('relative_humidity_pct')

    const comparison = screen.getByRole('region', { name: 'Sensor comparison' })
    await waitFor(() => expect(within(comparison).getAllByRole('row')).toHaveLength(7))
    for (const sensor of ['n1', 'n2', 'n3', 'n4', 'n5', 'n6']) {
      expect(within(comparison).getByText(sensor)).toBeVisible()
    }
    expect(screen.getByText('Exploratory candidates, not alert state.')).toBeVisible()
    expect(screen.getByText('No candidate outliers returned')).toBeVisible()
    expect(document.querySelector('input[type="file"]')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /upload|create alert|acknowledge|resolve/i })).not.toBeInTheDocument()
    expect(screen.queryByText(/notebook/i)).not.toBeInTheDocument()
  })

  it('restores URL filters and distinguishes absent samples from null fields with returned counts', async () => {
    setMockScenario('data-gap')
    renderEda(`/eda?sensor=n5&from=${from}&to=${to}&bucket=5m&model_version=model-v1`)

    expect(screen.getByRole('combobox', { name: 'Sensor' })).toHaveValue('n5')
    expect(screen.getByRole('textbox', { name: 'From' })).toHaveValue(from)
    expect(screen.getByRole('textbox', { name: 'To' })).toHaveValue(to)
    expect(screen.getByRole('combobox', { name: 'Bucket' })).toHaveValue('5m')

    const quality = screen.getByRole('region', { name: 'Quality and coverage' })
    await waitFor(() => expect(elementWithText(quality, '1 absent sample')).toBeVisible())
    expect(elementWithText(quality, '1 cadence gap')).toBeVisible()
    expect(screen.getByText('Null field values are counted separately from absent samples.')).toBeVisible()
    const missingness = screen.getByRole('region', { name: 'Missingness' })
    expect(elementWithText(missingness, 'temperature_c: 1 null field value (16.67%)')).toBeVisible()
    const temperatureImage = await screen.findByRole('img', { name: 'Temperature chart for sensor n5' })
    const humidityImage = screen.getByRole('img', { name: 'Relative humidity chart for sensor n5' })
    const scoreImage = screen.getByRole('img', { name: 'Anomaly score and threshold chart for sensor n5' })
    const temporal = screen.getByRole('region', { name: 'Temporal patterns' })
    const temporalCharts = within(temporal).getByRole('group', { name: 'Temporal charts for sensor n5' })
    expect(temporalCharts).not.toHaveStyle({ height: `${tokens.size.control * 12}px` })
    expect(temporalCharts).not.toHaveStyle({ overflow: 'hidden' })
    expect(elementWithText(temporal, '5 telemetry points returned')).toBeVisible()
    expect(elementWithText(temporal, '4 inference points returned')).toBeVisible()
    const charts = lineChartSpy.mock.calls.map(([props]) => props as LineChartProps)
    const temperatureChart = charts.find(
      (props) => props.id === 'temperature-chart-n5',
    )
    expect(temperatureChart).toMatchObject({
      title: 'Temperature',
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
      series: [{ id: 'temperature-series', connectNulls: false }],
    })
    expect(temperatureChart).not.toHaveProperty('role')
    expect(temperatureChart).not.toHaveProperty('aria-label')
    if (typeof temperatureChart?.desc !== 'string') throw new Error('Missing temperature chart description')
    expect(temperatureImage).toHaveAttribute('aria-description', temperatureChart.desc)
    expect(temperatureChart?.series[0]?.data).toContain(null)
    expect(temperatureChart?.xAxis?.[0]).not.toHaveProperty('zoom')
    const humidityChart = charts.find(
      (props) => props.id === 'humidity-chart-n5',
    )
    expect(humidityChart).toMatchObject({
      title: 'Relative humidity',
      height: tokens.size.control * 7,
      xAxis: [{
        id: 'humidity-x-axis',
        label: 'Date',
        scaleType: 'time',
        min: new Date(from),
        max: new Date(to),
      }],
    })
    expect(humidityChart).not.toHaveProperty('role')
    expect(humidityChart).not.toHaveProperty('aria-label')
    if (typeof humidityChart?.desc !== 'string') throw new Error('Missing humidity chart description')
    expect(humidityImage).toHaveAttribute('aria-description', humidityChart.desc)
    const scoreChart = charts.find(
      (props) => props.id === 'score-chart-n5',
    )
    expect(scoreChart).toMatchObject({
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
      series: [
        { id: 'score-series', color: theme.palette.warning.main, showMark: false },
        { id: 'threshold-series', color: theme.palette.text.secondary, showMark: false },
        { id: 'anomaly-series', color: theme.palette.error.main, shape: 'diamond', showMark: true },
      ],
    })
    expect(scoreChart).not.toHaveProperty('role')
     expect(scoreChart).not.toHaveProperty('aria-label')
     if (typeof scoreChart?.desc !== 'string') throw new Error('Missing score chart description')
     expect(scoreImage).toHaveAttribute('aria-description', scoreChart.desc)
     for (const chart of [temperatureChart, humidityChart, scoreChart]) {
       expect(chart).toHaveProperty('disableKeyboardNavigation', true)
     }
     expect(scoreChart?.series[1]?.data).toEqual(
      scoreChart?.series[0]?.data?.map(() => 0.8),
    )
    expect(await screen.findByRole('img', { name: /temperature_c distribution/i })).toBeVisible()
    const distributions = screen.getByRole('group', { name: 'Distribution panels' })
    expect([...distributions.querySelectorAll('p')].filter((element) => (
      element.textContent === '6 bounded samples returned'
    ))).toHaveLength(3)
    expect(await screen.findByRole('img', { name: /temperature_c by relative_humidity_pct scatter/i })).toBeVisible()
    const correlation = screen.getByRole('region', { name: 'Correlation and scatter' })
    expect(elementWithText(correlation, '1 scatter point returned from 1 bounded sample')).toBeVisible()
  })

  it('renders accessible chart wrappers while preserving MUI X chart metadata', async () => {
    server.use(
      http.get(`${origin}/api/eda/distributions`, ({ request }) => {
        const field = new URL(request.url).searchParams.get('field')
        return HttpResponse.json({
          request_id: `req_${field ?? 'distribution'}`,
          field,
          sample_count: 3,
          summary: { min: 0, max: 2, mean: 1, median: 1, p05: 0, p95: 2 },
          bins: [
            { start: 1, end: 2, count: 1 },
            { start: 0, end: 1, count: 2 },
          ],
        })
      }),
      http.get(`${origin}/api/eda/correlation`, () => HttpResponse.json({
        request_id: 'req_correlation_chart',
        x_field: 'temperature_c',
        y_field: 'relative_humidity_pct',
        sample_count: 4,
        correlation: -0.5,
        points: [
          {
            ts: '2026-07-19T10:20:00Z',
            device_id: 'n1',
            x: 24,
            y: 65,
            score: 0.2,
            is_candidate_outlier: false,
          },
          {
            ts: '2026-07-19T10:25:00Z',
            device_id: 'n6',
            x: 30,
            y: 50,
            score: 0.9,
            is_candidate_outlier: true,
          },
        ],
        next_cursor: null,
      })),
    )
    renderEda(`/eda?sensor=n5&from=${from}&to=${to}&bucket=5m`)

    await waitFor(() => expect(barChartSpy.mock.calls.length).toBeGreaterThanOrEqual(3))
    await waitFor(() => expect(scatterChartSpy).toHaveBeenCalled())

    const bars = barChartSpy.mock.calls.slice(-3).map(([props]) => props as BarChartProps)
    const temperature = bars.find(
      (props) => props.id === 'temperature_c-histogram-chart',
    )
    expect(temperature).toMatchObject({
      title: 'Temperature distribution',
      desc: expect.stringContaining('API order using [start, end) labels'),
      height: 264,
      hideLegend: true,
      skipAnimation: true,
      xAxis: [{
        id: 'temperature_c-histogram-x-axis',
        data: ['[1, 2)', '[0, 1)'],
        label: 'Bin range',
        scaleType: 'band',
        categoryGapRatio: 0,
      }],
      yAxis: [{ id: 'temperature_c-histogram-y-axis', label: 'Count' }],
      series: [{
        id: 'temperature_c-histogram-count-series',
        label: 'Count',
        color: theme.palette.primary.main,
        data: [1, 2],
      }],
    })
    for (const [id, label] of [
      ['temperature_c-histogram-chart', 'temperature_c distribution'],
      ['relative_humidity_pct-histogram-chart', 'relative_humidity_pct distribution'],
      ['score-histogram-chart', 'score distribution'],
    ] as const) {
       const chart = bars.find((props) => props.id === id)
       expect(chart).toHaveProperty('disableKeyboardNavigation', true)
       expect(chart).not.toHaveProperty('role')
      expect(chart).not.toHaveProperty('aria-label')
      if (typeof chart?.desc !== 'string') throw new Error(`Missing chart description for ${id}`)
      expect(screen.getByRole('img', { name: label })).toHaveAttribute('aria-description', chart.desc)
    }
    expect(bars.map((props) => props.series[0]?.color)).toEqual([
      theme.palette.primary.main,
      theme.palette.success.main,
      theme.palette.warning.main,
    ])

    const scatter = scatterChartSpy.mock.calls
      .map(([props]) => props as ScatterChartProps)
      .find((props) => props.id === 'correlation-scatter-chart')
     expect(scatter).toMatchObject({
       title: 'temperature_c by relative_humidity_pct scatter',
       desc: expect.stringMatching(/2 displayed points from 4 total bounded samples.*1 candidate outlier.*diamond.*circular/i),
       disableKeyboardNavigation: true,
       height: 308,
      skipAnimation: true,
      xAxis: [{ id: 'scatter-x-axis', label: 'temperature_c' }],
      yAxis: [{ id: 'scatter-y-axis', label: 'relative_humidity_pct' }],
      series: [
        {
          id: 'scatter-observation-series',
          label: 'Observations',
          color: theme.palette.info.main,
          data: [{ id: 'n1-2026-07-19T10:20:00Z-0', x: 24, y: 65 }],
        },
        {
          id: 'scatter-candidate-series',
          label: 'Candidate outliers (diamond)',
          color: theme.palette.error.main,
          data: [{ id: 'n6-2026-07-19T10:25:00Z-1', x: 30, y: 50 }],
        },
      ],
      slots: { marker: expect.any(Function) },
    })
    expect(scatter).not.toHaveProperty('role')
    expect(scatter).not.toHaveProperty('aria-label')
    if (typeof scatter?.desc !== 'string') throw new Error('Missing scatter chart description')
    expect(screen.getByRole('img', { name: 'temperature_c by relative_humidity_pct scatter' })).toHaveAttribute(
      'aria-description',
      scatter.desc,
    )

    const Marker = scatter?.slots?.marker
    if (Marker === undefined) throw new Error('Missing custom scatter marker slot')
    const markerProps: Omit<ScatterMarkerProps, 'seriesId'> = {
      color: theme.palette.info.main,
      dataIndex: 0,
      isFaded: false,
      isHighlighted: false,
      size: 5,
      x: 10,
      y: 10,
    }
    const markers = render(
      <svg>
        <Marker {...markerProps} seriesId="scatter-observation-series" />
        <Marker {...markerProps} seriesId="scatter-candidate-series" />
      </svg>,
    )
    expect(markers.container.querySelector('circle')).toBeInTheDocument()
    expect(markers.container.querySelector('rect')).toHaveAttribute(
      'transform',
      expect.stringContaining('rotate(45)'),
    )
    markers.unmount()
  })

  it('keeps EDA-local controls in Inter', async () => {
    renderEda(`/eda?sensor=n5&from=${from}&to=${to}&bucket=5m`)
    await screen.findByRole('img', { name: /temperature_c distribution/i })

    for (const control of [
      screen.getByRole('combobox', { name: 'Sensor' }),
      screen.getByRole('textbox', { name: 'From' }),
      screen.getByRole('textbox', { name: 'To' }),
      screen.getByRole('combobox', { name: 'Bucket' }),
      screen.getByRole('spinbutton', { name: 'Sample size' }),
      screen.getByRole('combobox', { name: 'X field' }),
      screen.getByRole('combobox', { name: 'Y field' }),
      screen.getByRole('spinbutton', { name: 'Bins' }),
    ]) {
      const inputRoot = control.closest('.MuiInputBase-root')
      if (inputRoot === null) throw new Error(`Missing input root for ${control.getAttribute('aria-label')}`)
      const style = getComputedStyle(inputRoot)
      expect(style.fontFamily).toContain('Inter')
      expect(style.fontVariantNumeric).toBe('normal')
    }
  })

  it('keeps Missingness prose in Inter and scopes technical values to Mono', async () => {
    setMockScenario('data-gap')
    renderEda(`/eda?sensor=n5&from=${from}&to=${to}&bucket=5m`)

    const missingness = await screen.findByRole('region', { name: 'Missingness' })
    let line: HTMLElement | undefined
    await waitFor(() => {
      line = elementWithText(missingness, 'temperature_c: 1 null field value (16.67%)')
    })
    if (line === undefined) throw new Error('Missing missingness summary')
    expect(getComputedStyle(line).fontFamily).toContain('Inter')

    for (const value of ['temperature_c', '1', '16.67%']) {
      const technicalValue = within(line).getByText(value)
      expect(getComputedStyle(technicalValue).fontFamily).toBe(tokens.font.data)
      expect(getComputedStyle(technicalValue).fontVariantNumeric).toContain('tabular-nums')
    }
  })

  it('keeps Temporal summary prose in Inter and scopes dynamic values to Mono', async () => {
    setMockScenario('data-gap')
    renderEda(`/eda?sensor=n5&from=${from}&to=${to}&bucket=5m`)
    await screen.findByRole('img', { name: 'Temperature chart for sensor n5' })

    const temporal = screen.getByRole('region', { name: 'Temporal patterns' })
    const summaryText = `Sensor n5 from ${from} to ${to}. 1 documented gap. Score threshold 0.8. 0 anomaly intervals. 0 detected alerts.`
    const summary = elementWithText(temporal, summaryText)
    expect(summary.textContent).toBe(summaryText)
    expect(getComputedStyle(summary).fontFamily).toContain('Inter')

    for (const value of ['n5', from, to, '0.8']) {
      const technicalValue = within(summary).getByText(value)
      expect(getComputedStyle(technicalValue).fontFamily).toBe(tokens.font.data)
      expect(getComputedStyle(technicalValue).fontVariantNumeric).toContain('tabular-nums')
    }
  })

  it('bounds local sample, bin, and scatter controls without adding them to the URL', async () => {
    renderEda(`/eda?sensor=n3&from=${from}&to=${to}&bucket=raw&model_version=model-v2`)
    await screen.findByRole('img', { name: /scatter/i })

    fireEvent.change(screen.getByRole('spinbutton', { name: 'Sample size' }), {
      target: { value: '9000' },
    })
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Bins' }), {
      target: { value: '2' },
    })
    expect(screen.getByRole('spinbutton', { name: 'Sample size' })).toHaveValue(5_000)
    expect(screen.getByRole('spinbutton', { name: 'Bins' })).toHaveValue(5)

    const user = userEvent.setup()
    await user.selectOptions(screen.getByRole('combobox', { name: 'X field' }), 'relative_humidity_pct')
    expect(screen.getByRole('combobox', { name: 'X field' })).toHaveValue('relative_humidity_pct')
    expect(screen.getByRole('combobox', { name: 'Y field' })).toHaveValue('temperature_c')

    await user.selectOptions(screen.getByRole('combobox', { name: 'Sensor' }), 'n2')
    const params = new URLSearchParams(screen.getByTestId('location-search').textContent ?? '')
    expect([...params.keys()].toSorted()).toEqual(['bucket', 'from', 'model_version', 'sensor', 'to'])
    expect(params.get('sensor')).toBe('n2')
    expect(params.get('model_version')).toBe('model-v2')
    expect(params.has('sampleSize')).toBe(false)
    expect(params.has('bins')).toBe(false)
    expect(params.has('x')).toBe(false)
    expect(params.has('y')).toBe(false)
  })

  it('keeps filters and unrelated panels visible when the summary query fails', async () => {
    server.use(
      http.get(`${origin}/api/eda/summary`, () =>
        HttpResponse.json(problem('req_eda_summary_failed'), { status: 503 }),
      ),
    )
    renderEda(`/eda?sensor=n2&from=${from}&to=${to}&bucket=5m`)

    expect((await screen.findAllByText(/req_eda_summary_failed/)).length).toBeGreaterThan(0)
    expect(screen.getByRole('combobox', { name: 'Sensor' })).toHaveValue('n2')
    for (const name of panelNames) {
      expect(screen.getByRole('heading', { level: 2, name })).toBeVisible()
    }
    expect(await screen.findByRole('img', { name: /temperature_c distribution/i })).toBeVisible()
    expect(await screen.findByRole('img', { name: /scatter/i })).toBeVisible()
    expect(await screen.findByRole('img', { name: 'Temperature chart for sensor n2' })).toBeVisible()
  })

  it('groups the approved EDA composition and preserves all five chart alternatives', async () => {
    renderEda(`/eda?sensor=n5&from=${from}&to=${to}&bucket=5m`)
    const quality = await screen.findByRole('group', { name: 'Quality and missingness' })
    expect(within(quality).getByRole('region', { name: 'Quality and coverage' })).toBeVisible()
    expect(within(quality).getByRole('region', { name: 'Missingness' })).toBeVisible()

    const distributions = await screen.findByRole('group', { name: 'Distribution panels' })
    for (const name of [
      'Temperature distribution',
      'Relative humidity distribution',
      'Anomaly score distribution',
    ]) {
      expect(within(distributions).getByRole('article', { name })).toBeVisible()
    }
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'Lihat data' })).toHaveLength(5))
  })
})

import { CssBaseline } from '@mui/material'
import { ThemeProvider } from '@mui/material/styles'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { activeDetectedAlert } from '../mocks/fixtures/alerts'
import {
  dataGapTelemetryHistoryPoints,
  fixtureGeneratedAt,
  latestTelemetrySensors,
  telemetryHistoryPoints,
} from '../mocks/fixtures/telemetry'
import { server } from '../mocks/node'
import { setMockScenario } from '../mocks/state'
import {
  createQueryTestHarness,
  type QueryTestHarness,
} from '../test/queryTestUtils'
import { theme } from '../theme/theme'
import { tokens } from '../theme/tokens'
import { OverviewPage } from './OverviewPage'

const fixedNow = '2026-07-19T10:30:00Z'
const inferenceFrom = '2026-07-19T10:00:00.000Z'
const inferenceTo = '2026-07-19T10:30:00.000Z'
const origin = window.location.origin

const { sparkLineChartSpy } = vi.hoisted(() => ({
  sparkLineChartSpy: vi.fn(),
}))

interface SparkLineChartMockProps {
  data: readonly number[]
  xAxis?: { data?: readonly Date[]; scaleType?: string }
  color?: string
  height?: number
  width?: number
}

vi.mock('@mui/x-charts/SparkLineChart', () => ({
  SparkLineChart: (props: SparkLineChartMockProps) => {
    sparkLineChartSpy(props)
    const { color, data, height, width, xAxis } = props
    return (
      <div
        data-testid="sparkline-chart"
        data-axis-scale={xAxis?.scaleType}
        data-color={color}
        data-date-axis={String(xAxis?.data?.every((value) => value instanceof Date) === true)}
        data-missing-gaps={Array.from(
          { length: data.length },
          (_, index) => data[index] === undefined,
        ).filter(Boolean).length}
        style={{ height, width }}
      />
    )
  },
}))

let harness: QueryTestHarness

function Providers({ children }: { children: ReactNode }) {
  const QueryProvider = harness.wrapper
  return (
    <QueryProvider>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <MemoryRouter>{children}</MemoryRouter>
      </ThemeProvider>
    </QueryProvider>
  )
}

function renderOverview() {
  return render(<OverviewPage />, { wrapper: Providers })
}

async function sensorArticles() {
  const articles = await screen.findAllByRole('article')
  expect(articles.map((article) => article.getAttribute('aria-label'))).toEqual([
    'Sensor n1',
    'Sensor n2',
    'Sensor n3',
    'Sensor n4',
    'Sensor n5',
    'Sensor n6',
  ])
  return articles
}

function summaryMetric(summary: HTMLElement, label: string) {
  const container = within(summary).getByText(label).parentElement
  if (container === null) throw new Error(`Summary metric ${label} has no container`)
  return within(container)
}

function definitionValue(scope: HTMLElement, label: string) {
  const term = Array.from(scope.querySelectorAll('dt')).find(
    (candidate) => candidate.textContent?.trim().replace(/:$/, '') === label,
  )
  if (!(term instanceof HTMLElement)) throw new Error(`Definition term ${label} was not found`)
  const value = term.nextElementSibling
  if (!(value instanceof HTMLElement) || value.tagName !== 'DD') {
    throw new Error(`Definition term ${label} has no associated dd`)
  }
  const list = term.closest('dl')
  if (!(list instanceof HTMLElement) || value.closest('dl') !== list) {
    throw new Error(`Definition term ${label} and its dd are not in the same dl`)
  }
  return value
}

function problem(requestId: string) {
  return {
    type: `https://example.invalid/problems/${requestId}`,
    title: 'Overview request failed',
    status: 503,
    detail: 'The overview resource is temporarily unavailable',
    instance: '/api/overview-test',
    request_id: requestId,
  }
}

beforeEach(() => {
  harness = createQueryTestHarness()
  sparkLineChartSpy.mockClear()
  vi.spyOn(Date, 'now').mockReturnValue(Date.parse(fixedNow))
})

afterEach(() => {
  harness.restore()
  vi.restoreAllMocks()
})

describe('OverviewPage action-first triage', () => {
  it('renders one ordered action-first active-anomaly overview for all six sensors', async () => {
    setMockScenario('active-anomaly')
    server.use(
      http.get(`${origin}/api/telemetry/history`, ({ request }) => {
        const sensorId = new URL(request.url).searchParams.get('device_id')
        return HttpResponse.json({
          request_id: `req_overview_history_${sensorId}`,
          device_id: sensorId,
          from: inferenceFrom,
          to: inferenceTo,
          bucket: 'raw',
          points: dataGapTelemetryHistoryPoints,
          next_cursor: null,
          returned_count: dataGapTelemetryHistoryPoints.length,
        })
      }),
    )
    renderOverview()

    const pageHeadings = screen.getAllByRole('heading', { level: 1, name: 'Overview' })
    expect(pageHeadings).toHaveLength(1)
    const summary = await screen.findByRole('region', { name: 'Operational summary' })
    await summaryMetric(summary, 'Active alerts').findByText('1')
    await summaryMetric(summary, 'Score availability').findByText('6/6')
    const queueHeading = screen.getByRole('heading', { level: 2, name: 'Attention queue' })
    const matrixHeading = screen.getByRole('heading', { level: 2, name: 'Sensor matrix' })
    expect(summary.compareDocumentPosition(queueHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(queueHeading.compareDocumentPosition(matrixHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(within(summary).getByText('Active alerts')).toBeVisible()
    expect(summaryMetric(summary, 'Active alerts').getByText('1')).toBeVisible()
    expect(within(summary).getByText('Score availability')).toBeVisible()
    expect(summaryMetric(summary, 'Score availability').getByText('6/6')).toBeVisible()
    expect(within(summary).getByText('Highest breach')).toBeVisible()
    const highestBreachValue = summaryMetric(summary, 'Highest breach').getByText('+0.16 · n4')
    expect(highestBreachValue).toBeVisible()
    expect(highestBreachValue).toHaveStyle({ color: theme.palette.error.main })
    for (const label of [
      'Active alerts',
      'Telemetry available',
      'Score availability',
      'Highest breach',
    ]) {
      expect(within(summary).getByText(label)).toHaveStyle({
        fontWeight: '700',
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
      })
    }
    for (const summaryValue of [
      summaryMetric(summary, 'Active alerts').getByText('1'),
      summaryMetric(summary, 'Telemetry available').getByText('6/6'),
      summaryMetric(summary, 'Score availability').getByText('6/6'),
      summaryMetric(summary, 'Highest breach').getByText('+0.16 · n4'),
    ]) {
      expect(summaryValue).toHaveStyle({
        fontFamily: tokens.font.data,
        fontSize: tokens.font.size.summaryValue,
        fontVariantNumeric: 'tabular-nums',
        lineHeight: tokens.font.lineHeight.summaryValue,
        overflowWrap: 'anywhere',
      })
    }
    const summaryGrid = summary.firstElementChild
    if (!(summaryGrid instanceof HTMLElement)) throw new Error('Operational summary has no grid')
    expect(summaryGrid.children).toHaveLength(4)
    expect(summary.querySelectorAll('.MuiCard-root')).toHaveLength(4)
    expect(summary.querySelectorAll('.MuiCardContent-root')).toHaveLength(4)

    const articles = await sensorArticles()
    const matrixGrid = matrixHeading.nextElementSibling
    if (!(matrixGrid instanceof HTMLElement)) throw new Error('Sensor matrix has no grid')
    expect(matrixGrid.children).toHaveLength(6)
    for (const article of articles) {
      expect(article).toHaveClass('MuiCard-root', 'MuiPaper-outlined')
      expect(article.querySelector('.MuiCardContent-root')).toBeInTheDocument()
      expect(article.querySelector('.MuiCardActions-root')).toBeInTheDocument()
    }
    const charts = await screen.findAllByRole('img', {
      name: /Recent (Temperature|RH) history for sensor/,
    })
    const chartLabels = ['n1', 'n2', 'n3', 'n4', 'n5', 'n6'].flatMap((sensorId) => [
      `Recent Temperature history for sensor ${sensorId}`,
      `Recent RH history for sensor ${sensorId}`,
    ])
    const chartDescriptions = ['n1', 'n2', 'n3', 'n4', 'n5', 'n6'].flatMap((sensorId) => [
      `Recent temperature history for sensor ${sensorId}.`,
      `Recent relative humidity history for sensor ${sensorId}.`,
    ])
    expect(charts).toHaveLength(12)
    expect(charts.map((chart) => chart.getAttribute('aria-label'))).toEqual(chartLabels)
    expect(charts.map((chart) => chart.getAttribute('aria-description'))).toEqual(
      chartDescriptions,
    )
    charts.forEach((chart) => {
      expect(chart).toHaveStyle({
        height: `${tokens.size.sparkline}px`,
        width: `${tokens.size.sparkline}px`,
      })
    })
    const renderedCharts = screen.getAllByTestId('sparkline-chart')
    expect(renderedCharts).toHaveLength(12)
    renderedCharts.forEach((chart, index) => {
      expect(chart).toHaveStyle({
        height: `${tokens.size.sparkline}px`,
        width: `${tokens.size.sparkline}px`,
      })
      expect(chart).toHaveAttribute('data-axis-scale', 'time')
      expect(chart).toHaveAttribute('data-date-axis', 'true')
      expect(chart).toHaveAttribute('data-missing-gaps', '1')
      expect(chart).toHaveAttribute(
        'data-color',
        index % 2 === 0 ? theme.palette.primary.main : theme.palette.success.main,
      )
    })
    expect(sparkLineChartSpy).toHaveBeenCalled()
    sparkLineChartSpy.mock.calls.forEach(([props]) => {
      expect(props).not.toHaveProperty('skipAnimation')
      expect(props).not.toHaveProperty('role')
      expect(props).not.toHaveProperty('aria-label')
      expect(props).toEqual(expect.objectContaining({
        height: tokens.size.sparkline,
        width: tokens.size.sparkline,
      }))
    })
    const n4 = within(articles[3])
    const anomalyChip = n4.getByText('Active anomaly').closest('.MuiChip-root')
    if (!(anomalyChip instanceof HTMLElement)) throw new Error('Active anomaly has no MUI Chip')
    expect(anomalyChip).toHaveClass('MuiChip-sizeSmall', 'MuiChip-colorError')
    expect(definitionValue(articles[3], 'State')).toHaveTextContent('Anomalous inference')
    const sensorDefinitions = [
      ['Temperature', '25.9 °C'],
      ['RH', '63.9 %'],
      ['Timestamp', '2026-07-19T10:29:40Z'],
      ['Age', '20 seconds'],
      ['Score', '0.96'],
      ['Threshold', '0.8'],
    ] as const
    for (const [label, expectedValue] of sensorDefinitions) {
      const sensorValue = definitionValue(articles[3], label)
      expect(sensorValue).toHaveTextContent(expectedValue)
      expect(sensorValue).toHaveStyle({
        fontFamily: tokens.font.data,
        fontVariantNumeric: 'tabular-nums',
        overflowWrap: 'anywhere',
      })
      const sensorLine = sensorValue.parentElement
      if (sensorLine === null) throw new Error('Sensor technical value has no label line')
      expect(getComputedStyle(sensorLine).fontFamily).toContain('Inter')
    }
    for (const label of ['Temperature', 'RH'] as const) {
      const metricValue = definitionValue(articles[3], label)
      expect.soft(metricValue).toHaveStyle({
        fontSize: tokens.font.size.sectionTitle,
        fontWeight: '700',
        lineHeight: tokens.font.lineHeight.sectionTitle,
      })
      const metricLabel = metricValue.previousElementSibling
      if (!(metricLabel instanceof HTMLElement) || metricLabel.tagName !== 'DT') {
        throw new Error(`Sensor metric ${label} has no associated dt`)
      }
      expect.soft(metricLabel).toHaveStyle({
        color: label === 'Temperature' ? theme.palette.primary.main : theme.palette.success.main,
        fontFamily: tokens.font.ui,
        fontSize: tokens.font.size.caption,
        textTransform: 'uppercase',
      })
    }
    const temperatureTile = definitionValue(articles[3], 'Temperature').parentElement
    const humidityTile = definitionValue(articles[3], 'RH').parentElement
    if (temperatureTile === null || humidityTile === null) {
      throw new Error('Sensor metric value has no tile')
    }
    expect(temperatureTile).not.toBe(humidityTile)

    const freshStatus = n4.getByRole('status', { name: 'Fresh telemetry' })
    const freshChip = within(freshStatus).getByText('Fresh telemetry').closest('.MuiChip-root')
    if (!(freshChip instanceof HTMLElement)) throw new Error('Fresh telemetry has no MUI Chip')
    expect(freshChip).toHaveClass('MuiChip-sizeSmall', 'MuiChip-colorSuccess')
    expect(freshChip).not.toHaveAttribute('href')
    expect(freshChip).not.toHaveAttribute('tabindex')
    expect(within(freshStatus).queryByRole('button')).not.toBeInTheDocument()
    expect(within(freshStatus).queryByRole('link')).not.toBeInTheDocument()

    const inspect = n4.getByRole('link', { name: 'Inspect sensor history' })
    expect(inspect).toHaveAttribute('href', '/sensors/n4?sensor=n4')
    expect(inspect).toHaveClass('MuiButton-root', 'MuiButton-outlined')
    const review = n4.getByRole('link', { name: 'Review active alert' })
    expect(review).toHaveAttribute('href', '/alerts?sensor=n4')
    expect(review).toHaveClass('MuiButton-root', 'MuiButton-text')
    const sensorLinks = inspect.parentElement
    if (sensorLinks === null) throw new Error('Sensor links have no row')
    expect(sensorLinks).toHaveClass('MuiCardActions-root')
    expect(sensorLinks).toHaveStyle({ flexWrap: 'wrap' })
    expect(inspect).not.toHaveClass('MuiButton-fullWidth')
    expect(within(articles[0]).getByRole('link', { name: 'Inspect sensor history' })).toHaveClass(
      'MuiButton-fullWidth',
    )

    const currentAlert = screen.getByRole('region', { name: 'Current alert for n4' })
    expect(currentAlert).toHaveClass('MuiCard-root', 'MuiPaper-outlined')
    expect(currentAlert.querySelector('.MuiCardContent-root')).toBeInTheDocument()
    expect(currentAlert.querySelector('.MuiCardActions-root')).toBeInTheDocument()
    expect(currentAlert).toHaveTextContent('Score: 0.96')
    expect(currentAlert).toHaveTextContent('Threshold: 0.8')
    expect(currentAlert).toHaveTextContent('Detected: 2026-07-19T10:20:00Z')
    const currentAlertView = within(currentAlert)
    for (const alertValue of [
      currentAlertView.getByText('0.96'),
      currentAlertView.getByText('0.8'),
      currentAlertView.getByText('2026-07-19T10:20:00Z'),
    ]) {
      expect(alertValue).toHaveStyle({
        fontFamily: tokens.font.data,
        fontVariantNumeric: 'tabular-nums',
        overflowWrap: 'anywhere',
      })
      const alertLine = alertValue.parentElement
      if (alertLine === null) throw new Error('Alert technical value has no label line')
      expect(getComputedStyle(alertLine).fontFamily).toContain('Inter')
    }
    const alertMetrics = currentAlertView.getByText('0.96').parentElement?.parentElement
    if (alertMetrics === null) throw new Error('Alert metrics have no row')
    if (alertMetrics === undefined) throw new Error('Alert metrics have no row')
    expect(alertMetrics).toHaveStyle({ flexWrap: 'wrap', gap: '12px' })
    const alertLinks = currentAlertView.getByRole('link', { name: 'Inspect sensor history' }).parentElement
    if (alertLinks === null) throw new Error('Alert links have no row')
    expect(alertLinks).toHaveStyle({ flexWrap: 'wrap', gap: '8px' })
    const currentAlertInspect = currentAlertView.getByRole('link', { name: 'Inspect sensor history' })
    const currentAlertReview = currentAlertView.getByRole('link', { name: 'Review active alert' })
    expect(currentAlertInspect).toHaveAttribute('href', '/sensors/n4?sensor=n4')
    expect(currentAlertReview).toHaveAttribute('href', '/alerts?sensor=n4')
    const acknowledge = currentAlertView.getByRole('button', { name: 'Acknowledge alert' })
    expect(acknowledge).toBeEnabled()
    const actionRow = acknowledge.parentElement
    if (actionRow === null) throw new Error('Alert actions have no row')
    expect(actionRow).toHaveStyle({ flexWrap: 'wrap', gap: '4px' })
    expect(screen.queryByRole('button', { name: /Resolve alert/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.queryByText(/raw telemetry/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/evaluation report/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/^EDA$/)).not.toBeInTheDocument()
  })

  it('creates the exact six stable non-polling inference and history queries plus detected alerts', async () => {
    setMockScenario('active-anomaly')
    const view = renderOverview()
    await sensorArticles()

    const inferenceQueries = harness.queryClient.getQueryCache().findAll({
      queryKey: ['inference', 'results'],
    })
    expect(inferenceQueries.map((query) => query.queryKey)).toEqual(
      ['n1', 'n2', 'n3', 'n4', 'n5', 'n6'].map((sensorId) => [
        'inference',
        'results',
        sensorId,
        inferenceFrom,
        inferenceTo,
        'raw',
        500,
        null,
        null,
      ]),
    )
    expect(inferenceQueries.every((query) => !('refetchInterval' in query.options))).toBe(true)
    const historyQueries = harness.queryClient.getQueryCache().findAll({
      queryKey: ['telemetry', 'history'],
    })
    expect(historyQueries.map((query) => query.queryKey)).toEqual(
      ['n1', 'n2', 'n3', 'n4', 'n5', 'n6'].map((sensorId) => [
        'telemetry',
        'history',
        sensorId,
        inferenceFrom,
        inferenceTo,
        'raw',
        500,
        null,
      ]),
    )
    expect(historyQueries.every((query) => !('refetchInterval' in query.options))).toBe(true)
    const alerts = harness.queryClient.getQueryCache().find({
      queryKey: ['alerts', 'current', null, 'detected', 1, 100],
      exact: true,
    })
    expect(alerts?.options).toHaveProperty('refetchInterval', 10_000)

    view.rerender(<OverviewPage />)
    expect(harness.queryClient.getQueryCache().findAll({
      queryKey: ['inference', 'results'],
    })).toHaveLength(6)
    expect(harness.queryClient.getQueryCache().findAll({
      queryKey: ['telemetry', 'history'],
    })).toHaveLength(6)
  })

  it('keeps canonical cards and explicit unknowns for partial reordered telemetry and empty inference', async () => {
    setMockScenario('empty')
    server.use(
      http.get(`${origin}/api/telemetry/latest`, () =>
        HttpResponse.json({
          request_id: 'req_partial_telemetry',
          generated_at: fixtureGeneratedAt,
          sensors: [latestTelemetrySensors[3], latestTelemetrySensors[0]],
        }),
      ),
    )
    renderOverview()

    const articles = await sensorArticles()
    const missingN2 = within(articles[1])
    expect(missingN2.getByRole('status', { name: 'Current status unknown' })).toBeVisible()
    expect(definitionValue(articles[1], 'Temperature')).toHaveTextContent('Unavailable')
    expect(definitionValue(articles[1], 'RH')).toHaveTextContent('Unavailable')
    expect(definitionValue(articles[1], 'Timestamp')).toHaveTextContent('Unavailable')
    expect(definitionValue(articles[1], 'Age')).toHaveTextContent('Unavailable')

    const n6 = within(articles[5])
    expect(n6.getByText('Inference unavailable')).toBeVisible()
    expect(n6.getByText('No score available')).toBeVisible()
    expect(await n6.findByRole('status', {
      name: 'No recent history available for sensor n6',
    })).toHaveTextContent('No recent history available')
    expect(getComputedStyle(n6.getByText('No score available')).fontFamily).toContain('Inter')
    expect(n6.queryByText('Score: 0')).not.toBeInTheDocument()
    const summary = screen.getByRole('region', { name: 'Operational summary' })
    await summaryMetric(summary, 'Score availability').findByText('5/6')
    expect(within(summary).getByText('Telemetry availability unknown')).toBeVisible()
    expect(summaryMetric(summary, 'Score availability').getByText('5/6')).toBeVisible()
    expect(summaryMetric(summary, 'Highest breach').getByText('Unknown')).toBeVisible()
  })

  it('reserves the sparkline region while history loads without hiding values or actions', async () => {
    let releaseHistory: () => void = () => {
      throw new Error('History response gate was not initialized')
    }
    const historyGate = new Promise<void>((resolve) => {
      releaseHistory = resolve
    })
    server.use(
      http.get(`${origin}/api/telemetry/history`, async () => {
        await historyGate
        return HttpResponse.json({
          request_id: 'req_overview_history',
          device_id: 'n1',
          from: inferenceFrom,
          to: inferenceTo,
          bucket: 'raw',
          points: telemetryHistoryPoints,
          next_cursor: null,
          returned_count: telemetryHistoryPoints.length,
        })
      }),
    )
    renderOverview()

    const n1 = await screen.findByRole('article', { name: 'Sensor n1' })
    expect(await within(n1).findByText('24.1 °C')).toBeVisible()
    expect(within(n1).getByRole('link', { name: 'Inspect sensor history' })).toBeVisible()
    const loading = within(n1).getByRole('status', {
      name: 'Loading recent history for sensor n1',
    })
    expect(loading).toHaveAttribute('aria-busy', 'true')
    expect(loading).toHaveStyle({ height: '100%' })

    releaseHistory()
    const charts = await within(n1).findAllByRole('img', {
      name: /Recent (Temperature|RH) history for sensor n1/,
    })
    expect(charts).toHaveLength(2)
    charts.forEach((chart) => {
      expect(chart).toHaveStyle({ height: `${tokens.size.sparkline}px` })
    })
  })

  it('degrades history errors in place without hiding latest telemetry or actions', async () => {
    server.use(
      http.get(`${origin}/api/telemetry/history`, () =>
        HttpResponse.json(problem('req_overview_history_failed'), { status: 503 }),
      ),
    )
    renderOverview()

    const n1 = await screen.findByRole('article', { name: 'Sensor n1' })
    expect(await within(n1).findByText('24.1 °C')).toBeVisible()
    expect(await within(n1).findByRole('status', {
      name: 'Recent history unavailable for sensor n1',
    })).toHaveTextContent('Recent history unavailable')
    expect(within(n1).getByRole('link', { name: 'Inspect sensor history' })).toHaveAttribute(
      'href',
      '/sensors/n1?sensor=n1',
    )
  })

  it('keeps telemetry availability unknown when six returned rows duplicate and omit canonical sensors', async () => {
    server.use(
      http.get(`${origin}/api/telemetry/latest`, () =>
        HttpResponse.json({
          request_id: 'req_duplicate_telemetry',
          generated_at: fixtureGeneratedAt,
          sensors: [
            latestTelemetrySensors[0],
            latestTelemetrySensors[0],
            latestTelemetrySensors[1],
            latestTelemetrySensors[2],
            latestTelemetrySensors[3],
            latestTelemetrySensors[4],
          ],
        }),
      ),
    )
    renderOverview()
    await waitFor(() => expect(harness.queryClient.getQueryData(['telemetry', 'latest', null])).toEqual(
      expect.objectContaining({ request_id: 'req_duplicate_telemetry' }),
    ))

    const summary = screen.getByRole('region', { name: 'Operational summary' })
    expect(within(summary).getByText('Telemetry availability unknown')).toBeVisible()
    expect(summaryMetric(summary, 'Telemetry availability unknown').getByText('Unknown')).toBeVisible()
  })

  it('counts telemetry available only for canonical online sensors with a timestamp', async () => {
    server.use(
      http.get(`${origin}/api/telemetry/latest`, () =>
        HttpResponse.json({
          request_id: 'req_timestamp_availability',
          generated_at: fixtureGeneratedAt,
          sensors: latestTelemetrySensors.map((sensor) =>
            sensor.device_id === 'n2'
              ? { ...sensor, ts: null, freshness: 'unknown', age_seconds: null }
              : sensor.device_id === 'n3'
                ? { ...sensor, availability: 'offline' }
                : sensor,
          ),
        }),
      ),
    )
    renderOverview()
    await waitFor(() => expect(harness.queryClient.getQueryData(['telemetry', 'latest', null])).toEqual(
      expect.objectContaining({ request_id: 'req_timestamp_availability' }),
    ))

    const summary = screen.getByRole('region', { name: 'Operational summary' })
    expect(summaryMetric(summary, 'Telemetry available').getByText('4/6')).toBeVisible()
  })

  it('prioritizes an anomalous score without inventing an active-alert link', async () => {
    setMockScenario('active-anomaly')
    server.use(
      http.get(`${origin}/api/alerts/current`, () =>
        HttpResponse.json({
          request_id: 'req_no_detected_alerts',
          generated_at: fixtureGeneratedAt,
          items: [],
          page: 1,
          page_size: 100,
          total: 0,
        }),
      ),
    )
    renderOverview()

    const n4 = await screen.findByRole('article', { name: 'Sensor n4' })
    expect(await within(n4).findByText('Anomalous inference')).toBeVisible()
    expect(within(n4).getByText('Active anomaly').closest('.MuiChip-colorError')).toBeVisible()
    expect(within(n4).queryByRole('link', { name: 'Review active alert' })).not.toBeInTheDocument()
  })

  it('reports the highest breach from anomalous entries, not positive non-anomalous inconsistencies', async () => {
    server.use(
      http.get(`${origin}/api/inference-results`, ({ request }) => {
        const sensorId = new URL(request.url).searchParams.get('device_id')
        const anomaly = sensorId === 'n4'
        const score = sensorId === 'n1' ? 0.99 : anomaly ? 0.96 : 0.31
        return HttpResponse.json({
          request_id: `req_inference_${sensorId}`,
          device_id: sensorId,
          model_version: 'model-v1',
          points: [{
            window_start_ts: '2026-07-19T10:15:00Z',
            window_end_ts: '2026-07-19T10:20:00Z',
            score,
            threshold: 0.8,
            is_anomaly: anomaly,
            model_version: 'model-v1',
            model_hash: 'sha256:model-v1',
            preprocessing_hash: 'sha256:preprocessing-v1',
            threshold_hash: 'sha256:threshold-v1',
          }],
          next_cursor: null,
          returned_count: 1,
        })
      }),
    )
    renderOverview()

    const summary = screen.getByRole('region', { name: 'Operational summary' })
    await summaryMetric(summary, 'Score availability').findByText('6/6')
    expect(summaryMetric(summary, 'Highest breach').getByText('+0.16 · n4')).toBeVisible()
  })

  it.each([
    ['stale', 'n2', 'Stale telemetry', '600 seconds', 'Offline sensor'],
    ['offline', 'n3', 'Offline sensor', '3600 seconds', 'Stale telemetry'],
  ] as const)(
    'keeps %s telemetry distinct from the other availability state',
    async (scenario, sensorId, expectedStatus, expectedAge, excludedStatus) => {
      setMockScenario(scenario)
      renderOverview()
      const card = await screen.findByRole('article', { name: `Sensor ${sensorId}` })

      expect(await within(card).findByRole('status', { name: expectedStatus })).toBeVisible()
      expect(definitionValue(card, 'Age')).toHaveTextContent(expectedAge)
      expect(within(card).queryByText(excludedStatus)).not.toBeInTheDocument()
      if (scenario === 'offline') {
        expect(definitionValue(card, 'Temperature')).toHaveTextContent('Unavailable')
        expect(definitionValue(card, 'RH')).toHaveTextContent('Unavailable')
      }
    },
  )

  it('shows telemetry initial failure without hiding the H1, alert section, or six cards', async () => {
    setMockScenario('active-anomaly')
    server.use(
      http.get(`${origin}/api/telemetry/latest`, () =>
        HttpResponse.json(problem('req_telemetry_initial'), { status: 503 }),
      ),
    )
    renderOverview()

    expect(screen.getByRole('heading', { level: 1, name: 'Overview' })).toBeVisible()
    expect(await screen.findByRole('alert')).toHaveTextContent('req_telemetry_initial')
    expect(screen.getByRole('heading', { level: 2, name: 'Attention queue' })).toBeVisible()
    expect(screen.getByRole('region', { name: 'Current alert for n4' })).toBeVisible()
    await sensorArticles()
  })

  it('shows alerts initial failure independently and never reports it as zero active alerts', async () => {
    server.use(
      http.get(`${origin}/api/alerts/current`, () =>
        HttpResponse.json(problem('req_alerts_initial'), { status: 503 }),
      ),
    )
    renderOverview()

    expect(await screen.findByRole('alert')).toHaveTextContent('req_alerts_initial')
    await sensorArticles()
    const summary = screen.getByRole('region', { name: 'Operational summary' })
    expect(within(summary).getByText('Active alerts')).toBeVisible()
    expect(within(summary).getByText('Unknown')).toBeVisible()
    expect(screen.getByRole('heading', { level: 2, name: 'Attention queue' })).toBeVisible()
  })

  it('keeps retained telemetry and alerts visible when both background refreshes fail', async () => {
    setMockScenario('active-anomaly')
    renderOverview()
    await sensorArticles()
    expect(await screen.findByRole('region', { name: 'Current alert for n4' })).toBeVisible()

    server.use(
      http.get(`${origin}/api/telemetry/latest`, () =>
        HttpResponse.json(problem('req_telemetry_refetch'), { status: 503 }),
      ),
      http.get(`${origin}/api/alerts/current`, () =>
        HttpResponse.json(problem('req_alerts_refetch'), { status: 503 }),
      ),
    )
    await harness.queryClient.refetchQueries({ queryKey: ['telemetry', 'latest', null], exact: true })
    await harness.queryClient.refetchQueries({
      queryKey: ['alerts', 'current', null, 'detected', 1, 100],
      exact: true,
    })

    await waitFor(() => expect(screen.getByText('Latest telemetry refresh failed')).toBeVisible())
    expect(screen.getByText('Current alerts refresh failed')).toBeVisible()
    expect(definitionValue(
      screen.getByRole('article', { name: 'Sensor n4' }),
      'Temperature',
    )).toHaveTextContent('25.9 °C')
    expect(screen.getByRole('region', { name: 'Current alert for n4' })).toBeVisible()
    expect(screen.queryByText('req_telemetry_refetch')).not.toBeInTheDocument()
    expect(screen.queryByText('req_alerts_refetch')).not.toBeInTheDocument()
  })

  it('acknowledges pessimistically and retries the exact failed command by keyboard', async () => {
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
          return HttpResponse.json(problem('req_ack_failed'), { status: 503 })
        }
        return HttpResponse.json({
          request_id: 'req_ack_success',
          alert_id: activeDetectedAlert.alert_id,
          status: 'acknowledged',
          event: {
            event_id: 'event_n4_ack_overview',
            alert_id: activeDetectedAlert.alert_id,
            event_ts: '2026-07-19T10:31:00.000Z',
            event_type: 'acknowledged',
            device_id: 'n4',
            actor: 'operator',
            note: null,
            inference_result_window_start_ts: '2026-07-19T10:15:00Z',
            inference_result_window_end_ts: '2026-07-19T10:20:00Z',
            inference_model_version: 'model-v1',
          },
          idempotent_replay: false,
        })
      }),
    )
    renderOverview()
    const acknowledge = await screen.findByRole('button', { name: 'Acknowledge alert' })
    const uuid = vi.spyOn(crypto, 'randomUUID').mockReturnValue('550e8400-e29b-41d4-a716-446655440000')
    const timestamp = vi
      .spyOn(Date.prototype, 'toISOString')
      .mockReturnValue('2026-07-19T10:31:00.000Z')
    const user = userEvent.setup()

    acknowledge.focus()
    await user.keyboard('{Enter}')
    await waitFor(() => expect(acknowledge).toBeDisabled())
    expect(screen.getByRole('region', { name: 'Current alert for n4' })).toHaveTextContent(
      'Active anomaly',
    )
    expect(requestBodies).toHaveLength(1)

    releaseResponse()
    const retry = await screen.findByRole('button', { name: 'Retry acknowledgement' })
    expect(acknowledge).toBeEnabled()
    retry.focus()
    await user.keyboard(' ')
    await waitFor(() => expect(requestBodies).toHaveLength(2))

    expect(requestBodies[1]).toBe(requestBodies[0])
    expect(JSON.parse(requestBodies[0])).toEqual({
      command_id: '550e8400-e29b-41d4-a716-446655440000',
      event_ts: '2026-07-19T10:31:00.000Z',
    })
    expect(uuid).toHaveBeenCalledOnce()
    expect(timestamp).toHaveBeenCalledOnce()
    expect(screen.queryByRole('button', { name: /Resolve alert/i })).not.toBeInTheDocument()
  })
})

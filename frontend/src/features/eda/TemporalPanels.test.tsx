import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '@mui/material/styles'
import { delay, http, HttpResponse } from 'msw'
import type { ReactElement } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { EdaSectionName } from '../../contracts/eda'
import {
  edaReadyMonthlyRun,
  edaSectionsByName,
} from '../../mocks/fixtures/eda'
import { server } from '../../mocks/node'
import { createQueryTestHarness, type QueryTestHarness } from '../../test/queryTestUtils'
import { theme } from '../../theme/theme'
import { TemporalCoveragePanel } from './TemporalCoveragePanel'
import { TemporalDistributionPanel } from './TemporalDistributionPanel'
import { WeekdayHourCoveragePanel } from './WeekdayHourCoveragePanel'

vi.mock('@mui/x-charts/LineChart', () => ({
  lineClasses: { line: 'MuiLineElement-root' },
  LineChart: ({
    id,
    title,
    series = [],
    yAxis = [],
  }: {
    id?: string
    title?: string
    series?: readonly { data?: readonly (number | null)[] }[]
    yAxis?: readonly { label?: string }[]
  }) => (
    <div
      role="img"
      aria-label={title}
      data-testid={id}
      data-series-count={series.length}
      data-first-series={JSON.stringify(series[0]?.data ?? [])}
      data-y-axis={yAxis[0]?.label}
    />
  ),
}))

const runId = edaReadyMonthlyRun.run_id
const harnesses: QueryTestHarness[] = []

function expectDescribedCharts(count: number) {
  const charts = screen.getAllByRole('img').filter((chart) => chart.hasAttribute('aria-description'))
  expect(charts).toHaveLength(count)
  for (const chart of charts) {
    expect(chart.getAttribute('aria-label')?.trim()).not.toBe('')
    expect(chart.getAttribute('aria-description')?.trim()).not.toBe('')
  }
}

function expectSingleOutlinedPanel(title: string) {
  const panel = screen.getByRole('heading', { name: title }).closest('section')
  expect(panel?.classList.contains('MuiPaper-outlined')).toBe(true)
  expect(panel?.querySelector('.MuiPaper-outlined')).toBeNull()
}

function renderPanel(panel: ReactElement) {
  const harness = createQueryTestHarness()
  harnesses.push(harness)
  const QueryProvider = harness.wrapper
  const result = render(
    <ThemeProvider theme={theme}>
      <QueryProvider>{panel}</QueryProvider>
    </ThemeProvider>,
  )
  return {
    ...result,
    rerenderPanel: (nextPanel: ReactElement) => result.rerender(
      <ThemeProvider theme={theme}>
        <QueryProvider>{nextPanel}</QueryProvider>
      </ThemeProvider>,
    ),
  }
}

afterEach(() => {
  for (const harness of harnesses.splice(0)) harness.restore()
})

function coverageBin(overrides: Record<string, unknown> = {}) {
  return {
    start: '2025-06-01T00:00:00+07:00',
    end: '2025-07-01T00:00:00+07:00',
    exposure_seconds: 2_592_000,
    full_bin_seconds: 2_592_000,
    expected_slots: 432_000,
    exact_pair_count: 475_200,
    view_pair_count: 475_200,
    coverage: 1.1,
    retention: 1,
    partial: false,
    from_censored: false,
    to_censored: false,
    eligible: { '0.50': true, '0.80': true, '0.95': true },
    complete: true,
    eligible_nonpartial_days: { '0.50': 30, '0.80': 30, '0.95': 30 },
    regime: { '0.50': 'dense', '0.80': 'dense', '0.95': 'dense' },
    ...overrides,
  }
}

const rawCoverageBin = coverageBin()
const screenedCoverageBin = coverageBin({
  view_pair_count: 427_680,
  retention: 0.9,
})
const rawHourlyCoverageBin = coverageBin({
  end: '2025-06-01T01:00:00+07:00',
  exposure_seconds: 3_600,
  full_bin_seconds: 3_600,
  expected_slots: 600,
  exact_pair_count: 660,
  view_pair_count: 660,
  eligible_nonpartial_days: undefined,
  complete: undefined,
  regime: undefined,
})
const screenedHourlyCoverageBin = coverageBin({
  end: '2025-06-01T01:00:00+07:00',
  exposure_seconds: 3_600,
  full_bin_seconds: 3_600,
  expected_slots: 600,
  exact_pair_count: 660,
  view_pair_count: 594,
  retention: 0.9,
  eligible_nonpartial_days: undefined,
  complete: undefined,
  regime: undefined,
})

const coveragePayload = {
  calendar_semantics: {
    timezone: 'Asia/Jakarta',
    bins: 'half_open',
    empty_bins_explicit: true,
    coverage_not_capped: true,
  },
  views: {
    resolved_raw_pairs: {
      hourly: [rawHourlyCoverageBin],
      daily: [rawCoverageBin],
      monthly: [rawCoverageBin],
      dense_regimes: {
        '0.50': [{ start: rawCoverageBin.start, end: rawCoverageBin.end, months: 3 }],
        '0.80': [{ start: rawCoverageBin.start, end: rawCoverageBin.end, months: 3 }],
        '0.95': [],
      },
    },
    rule_screened_pairs: {
      hourly: [screenedHourlyCoverageBin],
      daily: [screenedCoverageBin],
      monthly: [screenedCoverageBin],
      dense_regimes: { '0.50': [], '0.80': [], '0.95': [] },
    },
  },
}

function distributionBin(medianSuhu: number, medianRh: number) {
  return {
    start: '2025-06-01T00:00:00+07:00',
    end: '2025-07-01T00:00:00+07:00',
    view_pair_count: 10,
    from_censored: false,
    to_censored: false,
    statistics: {
      count: 10,
      suhu: { median: medianSuhu, q1: medianSuhu - 1, q3: medianSuhu + 1, mad: 1 },
      rh: { median: medianRh, q1: medianRh - 2, q3: medianRh + 2, mad: 2 },
    },
  }
}

const rawDistributionBin = distributionBin(25, 60)
const censoredRawDistributionBin = {
  ...distributionBin(24, 59),
  start: '2025-07-01T00:00:00+07:00',
  end: '2025-08-01T00:00:00+07:00',
  from_censored: true,
}
const screenedDistributionBin = distributionBin(23, 55)
const censoredScreenedDistributionBin = {
  ...distributionBin(22, 54),
  start: '2025-07-01T00:00:00+07:00',
  end: '2025-08-01T00:00:00+07:00',
  from_censored: true,
}
const distributionPayload = {
  cadence: { expected_seconds: 6, publication_gate: 'pass' },
  views: {
    resolved_raw_pairs: {
      hourly: [rawDistributionBin, censoredRawDistributionBin],
      daily: [rawDistributionBin, censoredRawDistributionBin],
      monthly: [rawDistributionBin, censoredRawDistributionBin],
      channels: { suhu: { name: 'Suhu', unit: '°C' }, rh: { name: 'RH', unit: '%' } },
      drift_conclusions: {
        suhu: { status: 'robust', directions: { '0.50': 'increase', '0.80': 'increase', '0.95': 'increase' } },
        rh: { status: 'insufficient_data', directions: { '0.50': 'insufficient_data' } },
      },
    },
    rule_screened_pairs: {
      hourly: [screenedDistributionBin, censoredScreenedDistributionBin],
      daily: [screenedDistributionBin, censoredScreenedDistributionBin],
      monthly: [screenedDistributionBin, censoredScreenedDistributionBin],
      channels: { suhu: { name: 'Suhu', unit: '°C' }, rh: { name: 'RH', unit: '%' } },
      drift_conclusions: {
        suhu: { status: 'not_robust', directions: { '0.50': 'increase', '0.80': 'stable', '0.95': 'decrease' } },
        rh: { status: 'insufficient_data', directions: { '0.50': 'insufficient_data' } },
      },
    },
  },
}

function completeSection(section: EdaSectionName) {
  const base = edaSectionsByName.get(section)
  if (base === undefined) throw new Error(`Missing fixture for ${section}`)
  return {
    ...base,
    payload: section === 'temporal_coverage' ? coveragePayload : distributionPayload,
  }
}

function serveCompleteSections() {
  server.use(http.get('/api/eda/runs/:runId/sections/:section', ({ params }) => (
    HttpResponse.json(completeSection(String(params.section) as EdaSectionName))
  )))
}

const panelCases = [
  {
    name: 'coverage',
    section: 'temporal_coverage' as const,
    panel: (id: string | null) => <TemporalCoveragePanel runId={id} />,
    loading: 'Memuat cakupan kalender temporal',
    empty: 'Tidak ada bin cakupan temporal',
    notEligible: 'Cakupan temporal belum memenuhi syarat',
  },
  {
    name: 'weekday-hour',
    section: 'temporal_coverage' as const,
    panel: (id: string | null) => <WeekdayHourCoveragePanel runId={id} />,
    loading: 'Memuat matriks hari dan jam',
    empty: 'Tidak ada baris per jam',
    notEligible: 'Matriks temporal belum memenuhi syarat',
  },
  {
    name: 'distribution',
    section: 'temporal_distribution' as const,
    panel: (id: string | null) => <TemporalDistributionPanel runId={id} />,
    loading: 'Memuat distribusi temporal',
    empty: 'Tidak ada statistik distribusi temporal',
    notEligible: 'Distribusi temporal belum memenuhi syarat',
  },
]

describe.each(panelCases)('$name panel states', ({ section, panel, loading, empty, notEligible }) => {
  it('renders the disabled empty state without a selected run', () => {
    renderPanel(panel(null))
    expect(screen.getByText('Pilih run EDA')).not.toBeNull()
  })

  it('renders loading while its own section request is pending', () => {
    server.use(http.get('/api/eda/runs/:runId/sections/:section', async () => {
      await delay('infinite')
      return HttpResponse.json({})
    }))
    renderPanel(panel(runId))
    expect(screen.getByText(loading)).not.toBeNull()
  })

  it('renders a retryable API error', async () => {
    server.use(http.get('/api/eda/runs/:runId/sections/:section', ({ request }) => (
      HttpResponse.json({
        type: 'about:blank',
        title: 'Temporal test failed',
        status: 500,
        detail: 'Bagian temporal tidak dapat dimuat.',
        instance: new URL(request.url).pathname,
        request_id: 'req-temporal-failed',
      }, { status: 500 })
    )))
    renderPanel(panel(runId))
    expect(await screen.findByText('Temporal test failed')).not.toBeNull()
    expect(screen.getByRole('button', { name: 'Retry' })).not.toBeNull()
  })

  it('renders an empty complete response', async () => {
    renderPanel(panel(runId))
    expect(await screen.findByText(empty)).not.toBeNull()
  })

  it('renders not-eligible detail instead of a chart', async () => {
    const base = edaSectionsByName.get(section)
    if (base === undefined) throw new Error(`Missing fixture for ${section}`)
    server.use(http.get('/api/eda/runs/:runId/sections/:section', () => HttpResponse.json({
      ...base,
      status: 'not_eligible',
      reason_code: section === 'temporal_coverage'
        ? 'no_exposed_calendar_bins'
        : 'insufficient_representative_cadence',
      detail: 'Bukti temporal belum cukup untuk bagian ini.',
      payload_sha256: null,
      payload: null,
    })))
    renderPanel(panel(runId))
    expect(await screen.findByText(notEligible)).not.toBeNull()
    expect(screen.getByText(/Bukti temporal belum cukup untuk bagian ini\./)).not.toBeNull()
  })

  it('closes an open data dialog when the selected run changes', async () => {
    const user = userEvent.setup()
    serveCompleteSections()
    const { rerenderPanel } = renderPanel(panel(runId))

    await user.click(await screen.findByRole('button', { name: 'Lihat data' }))
    expect(screen.getByRole('dialog')).not.toBeNull()
    rerenderPanel(panel('run-b02-temporal-replacement'))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })
})

describe('temporal panel evidence', () => {
  it('keeps every chart described and paired with bounded data', async () => {
    serveCompleteSections()
    renderPanel(<>
      <TemporalCoveragePanel runId={runId} />
      <WeekdayHourCoveragePanel runId={runId} />
      <TemporalDistributionPanel runId={runId} />
    </>)

    await waitFor(() => expect(screen.getAllByRole('button', { name: 'Lihat data' })).toHaveLength(3))
    expectSingleOutlinedPanel('Distribusi temporal Suhu dan RH')
    expectDescribedCharts(4)
  })

  it('renders uncapped coverage and weighted weekday-hour evidence', async () => {
    serveCompleteSections()
    renderPanel(
      <>
        <TemporalCoveragePanel runId={runId} />
        <WeekdayHourCoveragePanel runId={runId} />
      </>,
    )

    expect((await screen.findByTestId('temporal-coverage-monthly')).getAttribute('data-series-count')).toBe('4')
    expect((await screen.findAllByText('110%')).length).toBeGreaterThan(0)
    expect(screen.getByText(/kesimpulan pola stabil tidak ditampilkan/)).not.toBeNull()
  })

  it('renders three series per separate unit axis and switches raw/screened populations', async () => {
    const user = userEvent.setup()
    serveCompleteSections()
    renderPanel(<TemporalDistributionPanel runId={runId} />)

    const suhu = await screen.findByTestId('temporal-distribution-suhu')
    const rh = screen.getByTestId('temporal-distribution-rh')
    expect(suhu.getAttribute('data-series-count')).toBe('3')
    expect(rh.getAttribute('data-series-count')).toBe('3')
    expect(suhu.getAttribute('data-y-axis')).toBe('Suhu (°C)')
    expect(rh.getAttribute('data-y-axis')).toBe('RH (%)')
    expect(suhu.getAttribute('data-first-series')).toBe('[23,null]')
    expect(screen.getAllByText('1 bin tersensor dan 0 bin kosong memutus garis median, Q1, dan Q3.')).toHaveLength(2)

    await user.click(screen.getByLabelText('Populasi'))
    await user.click(screen.getByRole('option', { name: 'Pasangan exact mentah' }))
    await waitFor(() => expect(
      screen.getByTestId('temporal-distribution-suhu').getAttribute('data-first-series'),
    ).toBe('[25,null]'))
  })
})

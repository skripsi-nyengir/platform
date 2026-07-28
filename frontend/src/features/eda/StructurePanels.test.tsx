import { ThemeProvider } from '@mui/material/styles'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import type { ReactElement } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type {
  ChangePointsPayload,
  EdaSectionName,
  StationarityPayload,
} from '../../contracts/eda'
import { edaReadyMonthlyRun, edaSectionsByName } from '../../mocks/fixtures/eda'
import { server } from '../../mocks/node'
import { createQueryTestHarness, type QueryTestHarness } from '../../test/queryTestUtils'
import { theme } from '../../theme/theme'
import { AutocorrelationPanel } from './AutocorrelationPanel'
import { ChangePointPanel } from './ChangePointPanel'
import { SpectrumPanel } from './SpectrumPanel'
import { StationarityEligibilityPanel } from './StationarityEligibilityPanel'
import { StlDecompositionPanel } from './StlDecompositionPanel'

vi.mock('@mui/x-charts/LineChart', () => ({
  lineClasses: { line: 'MuiLineElement-root' },
  LineChart: ({
    id,
    title,
    series = [],
    sx = {},
    xAxis = [],
    yAxis = [],
  }: {
    id?: string
    title?: string
    series?: readonly {
      data?: readonly (number | null)[]
      valueFormatter?: (value: number | null) => string
    }[]
    sx?: Record<string, { display?: string }>
    xAxis?: readonly { data?: readonly unknown[] }[]
    yAxis?: readonly { label?: string; min?: number; max?: number; position?: string }[]
  }) => (
    <div
      role="img"
      aria-label={title}
      data-testid={id}
      data-series-count={series.length}
      data-first-series={JSON.stringify(series[0]?.data ?? [])}
      data-first-value-label={series[0]?.valueFormatter?.(series[0]?.data?.[0] ?? null)}
      data-line-hidden={Object.entries(sx).some(([selector, style]) => (
        selector.includes('MuiLineElement-root') && style.display === 'none'
      ))}
      data-x-count={xAxis[0]?.data?.length ?? 0}
      data-y-axis={yAxis[0]?.label}
      data-y-min={yAxis[0]?.min}
      data-y-max={yAxis[0]?.max}
      data-y-position={yAxis[0]?.position}
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
  const rendered = render(
    <ThemeProvider theme={theme}>
      <QueryProvider>{panel}</QueryProvider>
    </ThemeProvider>,
  )
  return {
    ...rendered,
    rerenderPanel(nextPanel: ReactElement) {
      rendered.rerender(
        <ThemeProvider theme={theme}>
          <QueryProvider>{nextPanel}</QueryProvider>
        </ThemeProvider>,
      )
    },
  }
}

afterEach(() => {
  for (const harness of harnesses.splice(0)) harness.restore()
})

function sequence(method: 'acf_fft' | 'pacf_ywm', scale = 1) {
  return {
    status: 'ok' as const,
    method,
    values: Array.from({ length: 73 }, (_, lag) => scale * (1 - lag / 72)),
    maximum_lag: 72,
    error: null,
  }
}

function stationarityPayload(): StationarityPayload {
  const hours = 336
  const values = Array.from({ length: hours }, (_, index) => index)
  const channel = (key: 'suhu' | 'rh') => ({
    autocorrelation: sequence('acf_fft', key === 'suhu' ? 1 : 0.8),
    partial_autocorrelation: sequence('pacf_ywm', key === 'suhu' ? 0.5 : 0.4),
    spectrum: {
      status: 'ok' as const,
      frequencies: [0, 1 / 24, 0.5],
      power: key === 'suhu' ? [1, 12, 2] : [2, 20, 3],
      error: null,
    },
    stl: {
      status: 'ok' as const,
      trend: values.map((value) => (key === 'suhu' ? 20 : 60) + value / 100),
      seasonal: values.map((value) => value % 24),
      residual: values.map(() => key === 'suhu' ? 0.1 : -0.2),
      error: null,
    },
  })
  return {
    eligibility_tier: 'sensitivity',
    primary: null,
    sensitivity: [{
      status: 'ok',
      start: '2025-07-01T00:00:00+07:00',
      end: '2025-07-15T00:00:00+07:00',
      hours,
      channels: { suhu: channel('suhu'), rh: channel('rh') },
    }],
  }
}

function changePointsPayload(): ChangePointsPayload {
  return {
    blocks: [{
      status: 'ok',
      pair_count: 100,
      start_day: 20_500,
      end_day: 20_599,
      scale_median: [25, 60],
      scale_mad: [0.5, 2],
      constant_channels: [],
      stable_changes: [{
        representative_day: 20_558,
        representative_boundary_index: 58,
        penalty_factors: [1, 2, 4, 8],
        observed_days: [20_557, 20_558, 20_559, 20_558],
        temperature_shift: -0.3,
        humidity_shift: -4,
        temperature_mad_effect: -0.6,
        humidity_mad_effect: -2,
      }, {
        representative_day: 20_531,
        representative_boundary_index: 31,
        penalty_factors: [1, 2, 4],
        observed_days: [20_530, 20_531, 20_532],
        temperature_shift: 0.4,
        humidity_shift: -3.5,
        temperature_mad_effect: 0.8,
        humidity_mad_effect: -1.75,
      }],
      confirmations: [{
        minimum_segment_days: 7,
        status: 'ok',
        requested_breakpoints: 2,
        boundary_days: [20_531, 20_558],
        matched_stable_changes: 2,
        error: null,
      }, {
        minimum_segment_days: 14,
        status: 'ok',
        requested_breakpoints: 2,
        boundary_days: [20_531, 20_558],
        matched_stable_changes: 2,
        error: null,
      }, {
        minimum_segment_days: 28,
        status: 'insufficient_data',
        requested_breakpoints: 2,
        boundary_days: [],
        matched_stable_changes: 0,
        error: 'requested breakpoints are infeasible',
      }],
    }],
  }
}

function completeSection(section: 'stationarity' | 'change_points', rich = true) {
  const base = edaSectionsByName.get(section)
  if (base === undefined) throw new Error(`Missing fixture for ${section}`)
  if (!rich) return base
  return {
    ...base,
    payload: section === 'stationarity' ? stationarityPayload() : changePointsPayload(),
  }
}

function serveCompleteSections(rich = true) {
  server.use(http.get('/api/eda/runs/:runId/sections/:section', ({ params }) => {
    const section = String(params.section) as 'stationarity' | 'change_points'
    return HttpResponse.json(completeSection(section, rich))
  }))
}

function ineligibleSection(section: 'stationarity' | 'change_points') {
  const base = edaSectionsByName.get(section)
  if (base === undefined) throw new Error(`Missing fixture for ${section}`)
  return {
    ...base,
    status: 'not_eligible',
    reason_code: section === 'stationarity'
      ? 'insufficient_stationarity_sensitivity_tier'
      : 'insufficient_daily_medians',
    detail: 'Run satu hari belum menyediakan agregat yang cukup.',
    payload_sha256: null,
    payload: null,
  }
}

const panelCases = [
  {
    name: 'eligibility',
    section: 'stationarity' as const,
    panel: (id: string | null) => <StationarityEligibilityPanel runId={id} />,
    heading: 'Kelayakan struktur temporal',
    loading: 'Memuat kelayakan struktur temporal',
    notEligible: 'Struktur temporal belum memenuhi syarat',
    dialogButton: 'Lihat data kelayakan struktur temporal',
  },
  {
    name: 'autocorrelation',
    section: 'stationarity' as const,
    panel: (id: string | null) => <AutocorrelationPanel runId={id} />,
    heading: 'Autokorelasi ACF dan PACF',
    loading: 'Memuat ACF dan PACF',
    notEligible: 'ACF/PACF belum memenuhi syarat',
    dialogButton: 'Lihat data autokorelasi ACF dan PACF',
  },
  {
    name: 'spectrum',
    section: 'stationarity' as const,
    panel: (id: string | null) => <SpectrumPanel runId={id} />,
    heading: 'Spektrum frekuensi',
    loading: 'Memuat spektrum frekuensi',
    notEligible: 'Spektrum belum memenuhi syarat',
    dialogButton: 'Lihat data spektrum frekuensi',
  },
  {
    name: 'STL',
    section: 'stationarity' as const,
    panel: (id: string | null) => <StlDecompositionPanel runId={id} />,
    heading: 'Dekomposisi STL',
    loading: 'Memuat dekomposisi STL',
    notEligible: 'STL belum memenuhi syarat',
    dialogButton: 'Lihat data dekomposisi STL',
  },
  {
    name: 'change points',
    section: 'change_points' as const,
    panel: (id: string | null) => <ChangePointPanel runId={id} />,
    heading: 'Kandidat perubahan rezim',
    loading: 'Memuat kandidat perubahan rezim',
    notEligible: 'Kandidat perubahan belum memenuhi syarat',
    dialogButton: 'Lihat data kandidat perubahan rezim',
  },
]

describe.each(panelCases)('$name panel states', ({ name, section, panel, heading, loading, notEligible }) => {
  it('renders its first-class section and disabled empty state without a run', () => {
    renderPanel(panel(null))
    expect(screen.getByRole('heading', { name: heading })).not.toBeNull()
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

  it('renders a retryable request error', async () => {
    server.use(http.get('/api/eda/runs/:runId/sections/:section', ({ request }) => (
      HttpResponse.json({
        type: 'about:blank',
        title: 'Structure test failed',
        status: 500,
        detail: 'Bagian struktur tidak dapat dimuat.',
        instance: new URL(request.url).pathname,
        request_id: 'req-structure-failed',
      }, { status: 500 })
    )))
    renderPanel(panel(runId))
    expect(await screen.findByText('Structure test failed')).not.toBeNull()
    expect(screen.getByRole('button', { name: 'Retry' })).not.toBeNull()
  })

  it('renders an explicit not-eligible state', async () => {
    server.use(http.get('/api/eda/runs/:runId/sections/:requestedSection', () => (
      HttpResponse.json(ineligibleSection(section))
    )))
    renderPanel(panel(runId))
    expect(await screen.findByText(notEligible)).not.toBeNull()
    expect(screen.getByText(/Run satu hari belum menyediakan agregat yang cukup\./)).not.toBeNull()
    if (section === 'change_points') {
      expect(screen.getByText(/Median harian belum cukup/)).not.toBeNull()
    }
    if (name === 'eligibility') {
      expect(screen.getByText('SENSITIVITY ≥ 336 jam').parentElement?.className).not.toContain('MuiChip-colorSuccess')
    }
  })

  it('renders a legitimate failed statistical section as retryable', async () => {
    const base = edaSectionsByName.get(section as EdaSectionName)
    if (base === undefined) throw new Error(`Missing fixture for ${section}`)
    server.use(http.get('/api/eda/runs/:runId/sections/:requestedSection', () => HttpResponse.json({
      ...base,
      status: 'failed',
      reason_code: 'section_compute_failed',
      detail: 'Perhitungan statistik struktur gagal.',
      payload_sha256: null,
      payload: null,
    })))
    renderPanel(panel(runId))
    expect(await screen.findByText('Perhitungan statistik struktur gagal.')).not.toBeNull()
    expect(screen.getByRole('button', { name: 'Retry' })).not.toBeNull()
  })
})

describe.each(panelCases)('$name panel audit dialog', ({ panel, dialogButton }) => {
  it('uses a panel-specific dialog trigger', async () => {
    serveCompleteSections()
    renderPanel(panel(runId))

    const trigger = await screen.findByRole('button', { name: dialogButton })
    expect(trigger.getAttribute('aria-haspopup')).toBe('dialog')
  })

  it('stays closed after switching away from and back to a run', async () => {
    const user = userEvent.setup()
    serveCompleteSections()
    const rendered = renderPanel(panel(runId))

    const triggerLabel = await screen.findByText('Lihat data')
    const trigger = triggerLabel.closest('button')
    if (trigger === null) throw new Error('Expected dialog trigger button')
    await user.click(trigger)
    expect(screen.getByRole('dialog')).not.toBeNull()

    rendered.rerenderPanel(panel('11111111-1111-4111-8111-111111111111'))
    expect(screen.queryByRole('dialog')).toBeNull()
    rendered.rerenderPanel(panel(runId))
    await screen.findByText('Lihat data')
    expect(screen.queryByRole('dialog')).toBeNull()
  })
})

describe('complete structure evidence', () => {
  it('keeps every chart described and every panel paired with bounded data', async () => {
    serveCompleteSections()
    renderPanel(<>
      <StationarityEligibilityPanel runId={runId} />
      <AutocorrelationPanel runId={runId} />
      <SpectrumPanel runId={runId} />
      <StlDecompositionPanel runId={runId} />
      <ChangePointPanel runId={runId} />
    </>)

    await waitFor(() => expect(screen.getAllByRole('button', { name: /^Lihat data/ })).toHaveLength(5))
    expectSingleOutlinedPanel('Autokorelasi ACF dan PACF')
    expectSingleOutlinedPanel('Spektrum frekuensi')
    expectSingleOutlinedPanel('Dekomposisi STL')
    expectSingleOutlinedPanel('Kandidat perubahan rezim')
    expectDescribedCharts(11)
  })

  it('renders the eligibility tier and method without a binary stationarity conclusion', async () => {
    serveCompleteSections()
    renderPanel(<StationarityEligibilityPanel runId={runId} />)

    expect(await screen.findByText('SENSITIVITY')).not.toBeNull()
    expect(screen.getByText('Median per jam')).not.toBeNull()
    expect(screen.getByText('336 jam')).not.toBeNull()
    expect(screen.getByText(/hipotesis nol berbeda/)).not.toBeNull()
    expect(screen.queryByText(/^Stasioner$/i)).toBeNull()
  })

  it('renders separate Suhu and RH ACF/PACF charts with 73 lags and fixed domains', async () => {
    serveCompleteSections()
    renderPanel(<AutocorrelationPanel runId={runId} />)

    const suhu = await screen.findByTestId('autocorrelation-suhu')
    const rh = screen.getByTestId('autocorrelation-rh')
    for (const chart of [suhu, rh]) {
      expect(chart.getAttribute('data-series-count')).toBe('2')
      expect(chart.getAttribute('data-x-count')).toBe('73')
      expect(chart.getAttribute('data-y-min')).toBe('-1')
      expect(chart.getAttribute('data-y-max')).toBe('1')
    }
    expect(screen.getByText(/tanpa pita kepercayaan/)).not.toBeNull()
    expect(screen.getByText(/tanpa rekomendasi orde model/)).not.toBeNull()
  })

  it('renders separate channel spectra and the trend/window/aggregation warning', async () => {
    serveCompleteSections()
    renderPanel(<SpectrumPanel runId={runId} />)

    expect((await screen.findByTestId('spectrum-suhu')).getAttribute('data-series-count')).toBe('1')
    expect(screen.getByTestId('spectrum-rh').getAttribute('data-series-count')).toBe('1')
    expect(screen.getByText(/tren, jendela analisis, atau agregasi/)).not.toBeNull()
  })

  it('renders aligned three-line STL charts per channel with the fixed 24-hour notice', async () => {
    serveCompleteSections()
    renderPanel(<StlDecompositionPanel runId={runId} />)

    expect((await screen.findByTestId('stl-suhu')).getAttribute('data-series-count')).toBe('3')
    expect(screen.getByTestId('stl-rh').getAttribute('data-series-count')).toBe('3')
    expect(screen.getByText(/periode tetap 24 jam/)).not.toBeNull()
    expect(screen.getByText(/bukan klaim siklus fisik/)).not.toBeNull()
  })

  it('renders historical candidate markers and four unit-separated shift/effect charts', async () => {
    serveCompleteSections()
    renderPanel(<ChangePointPanel runId={runId} />)

    const candidateDates = await screen.findByTestId('change-point-dates')
    const suhuShift = screen.getByTestId('change-point-suhu-shift')
    const rhShift = screen.getByTestId('change-point-rh-shift')
    const suhuEffect = screen.getByTestId('change-point-suhu-effect')
    const rhEffect = screen.getByTestId('change-point-rh-effect')
    expect(candidateDates.getAttribute('data-x-count')).toBe('2')
    expect(candidateDates.getAttribute('data-y-position')).toBe('none')
    expect(candidateDates.getAttribute('data-first-value-label')).toBe('Kandidat stabil')
    for (const chart of [candidateDates, suhuShift, rhShift, suhuEffect, rhEffect]) {
      expect(chart.getAttribute('data-line-hidden')).toBe('true')
    }
    expect(suhuShift.getAttribute('data-y-axis')).toBe('Perubahan Suhu (°C)')
    expect(rhShift.getAttribute('data-y-axis')).toBe('Perubahan RH (%)')
    expect(suhuEffect.getAttribute('data-y-axis')).toBe('Efek Suhu (MAD)')
    expect(rhEffect.getAttribute('data-y-axis')).toBe('Efek RH (MAD)')
    expect(screen.getByText(/4 penalti stabil/)).not.toBeNull()
    expect(screen.getByText(/agregat harian, bukan timestamp kejadian/)).not.toBeNull()
    expect(window.getComputedStyle(screen.getByText(/minimum segmen 7 hari/)).whiteSpace).toBe('normal')
  })

  it('opens bounded audit data without adding audit fields to chart payloads', async () => {
    const user = userEvent.setup()
    serveCompleteSections()
    renderPanel(<ChangePointPanel runId={runId} />)

    await user.click(await screen.findByRole('button', { name: 'Lihat data kandidat perubahan rezim' }))
    expect(screen.getByRole('dialog')).not.toBeNull()
    expect(screen.getByText(/bounded records returned/)).not.toBeNull()
    expect(screen.getByText('Skala median Suhu (°C)')).not.toBeNull()
    expect(screen.getByText('Skala median RH (%)')).not.toBeNull()
    expect(screen.getByText('Skala MAD Suhu (°C)')).not.toBeNull()
    expect(screen.getByText('Skala MAD RH (%)')).not.toBeNull()
  })
})

describe('ineligible and constant structure evidence', () => {
  it('keeps all five one-day panels visible as explicit not-eligible cards', async () => {
    server.use(http.get('/api/eda/runs/:runId/sections/:section', ({ params }) => (
      HttpResponse.json(ineligibleSection(String(params.section) as 'stationarity' | 'change_points'))
    )))
    renderPanel(<>
      <StationarityEligibilityPanel runId={runId} />
      <AutocorrelationPanel runId={runId} />
      <SpectrumPanel runId={runId} />
      <StlDecompositionPanel runId={runId} />
      <ChangePointPanel runId={runId} />
    </>)

    for (const { heading, notEligible } of panelCases) {
      expect(await screen.findByRole('heading', { name: heading })).not.toBeNull()
      expect(await screen.findByText(notEligible)).not.toBeNull()
    }
    expect(screen.queryAllByRole('img')).toHaveLength(0)
  })

  it('renders explicit constant-channel and no-candidate cards instead of empty charts', async () => {
    serveCompleteSections(false)
    renderPanel(<>
      <AutocorrelationPanel runId={runId} />
      <SpectrumPanel runId={runId} />
      <StlDecompositionPanel runId={runId} />
      <ChangePointPanel runId={runId} />
    </>)

    expect(await screen.findByText('ACF/PACF Suhu tidak memenuhi syarat: kanal konstan.')).not.toBeNull()
    expect(screen.getByText('Spektrum Suhu tidak memenuhi syarat: kanal konstan.')).not.toBeNull()
    expect(screen.getByText('STL Suhu tidak memenuhi syarat: kanal konstan.')).not.toBeNull()
    expect(screen.getByText('Tidak ada kandidat perubahan stabil')).not.toBeNull()
    expect(screen.getByText(/Blok harian berstatus constant/)).not.toBeNull()
  })
})

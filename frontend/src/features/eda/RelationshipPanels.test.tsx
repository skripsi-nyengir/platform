import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '@mui/material/styles'
import { delay, http, HttpResponse } from 'msw'
import type { ReactElement } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { EdaSectionName, EdaSectionResponse } from '../../contracts/eda'
import { edaReadyMonthlyRun, edaSectionsByName } from '../../mocks/fixtures/eda'
import { server } from '../../mocks/node'
import { createQueryTestHarness, type QueryTestHarness } from '../../test/queryTestUtils'
import { theme } from '../../theme/theme'
import { AssociationSummaryPanel } from './AssociationSummaryPanel'
import { BootstrapUncertaintyPanel } from './BootstrapUncertaintyPanel'
import { RollingCorrelationPanel } from './RollingCorrelationPanel'

vi.mock('@mui/x-charts/LineChart', () => ({
  lineClasses: { line: 'MuiLineElement-root' },
  LineChart: ({
    id,
    title,
    series = [],
    xAxis = [],
    yAxis = [],
  }: {
    id?: string
    title?: string
    series?: readonly { data?: readonly (number | null)[] }[]
    xAxis?: readonly { data?: readonly unknown[] }[]
    yAxis?: readonly { min?: number; max?: number }[]
  }) => (
    <div
      role="img"
      aria-label={title}
      data-testid={id}
      data-first-series={JSON.stringify(series[0]?.data ?? [])}
      data-x-axis={JSON.stringify(xAxis[0]?.data ?? [])}
      data-y-min={yAxis[0]?.min}
      data-y-max={yAxis[0]?.max}
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
  return render(
    <ThemeProvider theme={theme}>
      <QueryProvider>{panel}</QueryProvider>
    </ThemeProvider>,
  )
}

afterEach(() => {
  for (const harness of harnesses.splice(0)) harness.restore()
})

function section(name: EdaSectionName): EdaSectionResponse {
  const value = edaSectionsByName.get(name)
  if (value === undefined) throw new Error(`Missing fixture for ${name}`)
  return value
}

function serve(valueFor: (name: EdaSectionName) => EdaSectionResponse = section) {
  server.use(http.get('/api/eda/runs/:runId/sections/:section', ({ params }) => (
    HttpResponse.json(valueFor(String(params.section) as EdaSectionName))
  )))
}

const panelCases = [
  {
    name: 'association',
    section: 'relationships' as const,
    panel: (id: string | null) => <AssociationSummaryPanel runId={id} />,
    loading: 'Memuat ringkasan asosiasi',
    notEligible: 'Ringkasan asosiasi belum memenuhi syarat',
  },
  {
    name: 'rolling',
    section: 'relationships' as const,
    panel: (id: string | null) => <RollingCorrelationPanel runId={id} />,
    loading: 'Memuat korelasi Pearson bergulir',
    notEligible: 'Korelasi bergulir belum memenuhi syarat',
  },
  {
    name: 'bootstrap',
    section: 'uncertainty' as const,
    panel: (id: string | null) => <BootstrapUncertaintyPanel runId={id} />,
    loading: 'Memuat ketidakpastian bootstrap',
    notEligible: 'Bootstrap belum memenuhi syarat',
  },
]

describe.each(panelCases)('$name panel lifecycle', ({ section: sectionName, panel, loading, notEligible }) => {
  it('renders an empty selection state without requesting data', () => {
    renderPanel(panel(null))
    expect(screen.getByText('Pilih run EDA')).not.toBeNull()
  })

  it('renders loading for its own section request', () => {
    server.use(http.get('/api/eda/runs/:runId/sections/:section', async () => {
      await delay('infinite')
      return HttpResponse.json({})
    }))
    renderPanel(panel(runId))
    expect(screen.getByText(loading)).not.toBeNull()
  })

  it('renders a retryable transport error', async () => {
    server.use(http.get('/api/eda/runs/:runId/sections/:section', ({ request }) => (
      HttpResponse.json({
        type: 'about:blank',
        title: 'Relationship test failed',
        status: 500,
        detail: 'Bagian hubungan tidak dapat dimuat.',
        instance: new URL(request.url).pathname,
        request_id: 'req-relationship-failed',
      }, { status: 500 })
    )))
    renderPanel(panel(runId))
    expect(await screen.findByText('Relationship test failed')).not.toBeNull()
    expect(screen.getByRole('button', { name: 'Retry' })).not.toBeNull()
  })

  it('renders section-level not-eligible detail', async () => {
    serve((name) => {
      const base = section(name)
      if (name !== sectionName) return base
      return {
        ...base,
        status: 'not_eligible',
        reason_code: name === 'relationships'
          ? 'insufficient_nonconstant_pairs'
          : 'block_longer_than_run',
        detail: 'Bukti statistik belum cukup untuk bagian ini.',
        payload_sha256: null,
        payload: null,
      } as EdaSectionResponse
    })
    renderPanel(panel(runId))
    expect(await screen.findByText(notEligible)).not.toBeNull()
    expect(screen.getByText(/Bukti statistik belum cukup untuk bagian ini\./)).not.toBeNull()
    if (sectionName === 'uncertainty') {
      expect(screen.getByText(/Blok lebih panjang daripada run/)).not.toBeNull()
    }
  })

  it('renders a legitimate failed optional section as retryable', async () => {
    serve((name) => {
      const base = section(name)
      if (name !== sectionName) return base
      return {
        ...base,
        status: 'failed',
        reason_code: 'section_compute_failed',
        detail: 'Perhitungan bagian opsional gagal.',
        payload_sha256: null,
        payload: null,
      } as EdaSectionResponse
    })
    renderPanel(panel(runId))
    expect(await screen.findByText('Perhitungan bagian opsional gagal.')).not.toBeNull()
    expect(screen.getByRole('button', { name: 'Retry' })).not.toBeNull()
  })
})

describe('relationship panel evidence', () => {
  it('renders both association coefficients on a fixed coefficient domain', async () => {
    serve()
    renderPanel(<AssociationSummaryPanel runId={runId} />)

    const chart = await screen.findByTestId('association-summary-chart')
    expect(chart.getAttribute('data-y-min')).toBe('-1')
    expect(chart.getAttribute('data-y-max')).toBe('1')
    expect(chart.getAttribute('data-x-axis')).toBe('["Mentah","Screened"]')
    expect(screen.getByText(/Pearson mengukur hubungan linear/)).not.toBeNull()
    expect(screen.getByText(/populasi terpilih yang berbeda/)).not.toBeNull()
    expectSingleOutlinedPanel('Ringkasan asosiasi Suhu–RH')
  })

  it('defaults to 30m/30s, keeps [-1,1], and updates both sensitivity selectors', async () => {
    const user = userEvent.setup()
    serve()
    renderPanel(<RollingCorrelationPanel runId={runId} />)

    const chart = await screen.findByTestId('rolling-correlation-chart')
    expect(chart.getAttribute('data-y-min')).toBe('-1')
    expect(chart.getAttribute('data-y-max')).toBe('1')
    expect(screen.getByText('Jendela 30 menit · batas gap 30 detik')).not.toBeNull()
    expect(screen.getByText(/jendela bergulir saling tumpang tindih/i)).not.toBeNull()

    await user.click(screen.getByLabelText('Jendela'))
    await user.click(screen.getByRole('option', { name: '60 menit' }))
    expect(await screen.findByText('Jendela 60 menit · batas gap 30 detik')).not.toBeNull()

    await user.click(screen.getByLabelText('Batas gap'))
    await user.click(screen.getByRole('option', { name: '15 detik' }))
    expect(await screen.findByText('Jendela 30 menit · batas gap 15 detik')).not.toBeNull()
  })

  it('renders per-block not-eligible bootstrap rows without whiskers', async () => {
    serve((name) => {
      const base = section(name)
      if (base.status !== 'complete' || base.section !== 'uncertainty') return base
      return {
        ...base,
        payload: {
          ...base.payload,
          blocks: {
            ...base.payload.blocks,
            '28': {
              status: 'not_eligible',
              reason_code: 'block_longer_than_run',
              intervals: base.payload.blocks['28'].intervals.map((item) => ({
                ...item,
                status: 'constant',
                replicate_count: 0,
                estimate: null,
                lower: null,
                upper: null,
              })),
            },
          },
        },
      } as EdaSectionResponse
    })
    renderPanel(<BootstrapUncertaintyPanel runId={runId} />)

    expect(await screen.findByText(/populasi median harian berpasangan/)).not.toBeNull()
    expect(screen.getAllByText('Tidak memenuhi syarat')).toHaveLength(2)
    expect(screen.getByTestId('bootstrap-whisker-7-pearson')).not.toBeNull()
    expect(screen.getByRole('img', { name: /interval bootstrap Pearson blok 7 hari/i })).not.toBeNull()
    expect(screen.getAllByText('Hari berpasangan / run').length).toBeGreaterThan(1)
    expect(screen.queryByTestId('bootstrap-whisker-28-pearson')).toBeNull()
    expect(screen.queryByTestId('bootstrap-whisker-28-spearman')).toBeNull()
  })

  it('opens bounded data from every complete panel', async () => {
    const user = userEvent.setup()
    serve()
    renderPanel(
      <>
        <AssociationSummaryPanel runId={runId} />
        <RollingCorrelationPanel runId={runId} />
        <BootstrapUncertaintyPanel runId={runId} />
      </>,
    )

    await waitFor(() => expect(
      screen.getAllByRole('button', { name: /^Lihat data/ }),
    ).toHaveLength(3))
    expect(screen.getByRole('button', { name: 'Lihat data ringkasan asosiasi' })).not.toBeNull()
    expect(screen.getByRole('button', { name: 'Lihat data korelasi bergulir' })).not.toBeNull()
    expect(screen.getByRole('button', { name: 'Lihat data bootstrap' })).not.toBeNull()
    expectDescribedCharts(8)
    const buttons = screen.getAllByRole('button', { name: /^Lihat data/ })
    await user.click(buttons[0]!)
    await waitFor(() => expect(screen.getByRole('dialog')).not.toBeNull())
  })
})

import { ThemeProvider } from '@mui/material/styles'
import { cleanup, render, screen } from '@testing-library/react'
import type { ComponentType } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../api/errors'
import type { EdaSectionName, EdaSectionResponse } from '../../contracts/eda'
import { edaSectionsByName } from '../../mocks/fixtures/eda'
import { theme } from '../../theme/theme'
import { JointDensityPanel } from './JointDensityPanel'
import { PairingAuditPanel } from './PairingAuditPanel'
import { QualityExcerptPanel } from './QualityExcerptPanel'
import { QualityIntegrityPanel } from './QualityIntegrityPanel'
import { UnivariateDiagnosticsPanel } from './UnivariateDiagnosticsPanel'

const useEdaSectionQueryMock = vi.hoisted(() => vi.fn())

vi.mock('./queries', () => ({
  useEdaSectionQuery: useEdaSectionQueryMock,
}))

interface PanelProps {
  runId: string | null
}

interface QueryState {
  data: EdaSectionResponse | undefined
  isError: boolean
  error: ApiError
  refetch: ReturnType<typeof vi.fn>
}

const apiError = new ApiError('network', 'quality endpoint unavailable')
const loadingState: QueryState = {
  data: undefined,
  isError: false,
  error: apiError,
  refetch: vi.fn(),
}

function expectDescribedCharts(count: number) {
  const charts = screen.getAllByRole('img').filter((chart) => chart.hasAttribute('aria-description'))
  expect(charts).toHaveLength(count)
  for (const chart of charts) {
    expect(chart.getAttribute('aria-label')?.trim()).not.toBe('')
    expect(chart.getAttribute('aria-description')?.trim()).not.toBe('')
  }
}

function section(name: EdaSectionName): Extract<EdaSectionResponse, { status: 'complete' }> {
  const value = edaSectionsByName.get(name)
  if (value === undefined) throw new Error(`Missing fixture section ${name}`)
  return value
}

const qualityResponse = {
  ...section('quality_overview'),
  section: 'quality_overview',
  payload: {
    source_audit: {
      row_count: 120,
      union_timestamps: 62,
      intersection_timestamps: 60,
      missing_idx0_timestamps: 1,
      missing_idx1_timestamps: 1,
      duplicate_group_count: 2,
      conflicting_duplicate_pair_count: 1,
      exact_pair_count: 60,
      rule_screened_pair_count: 58,
      observed_median_positive_delta_at_most_gap: 6,
      gap_above_primary_count: 2,
      cadence_gate: 'pass',
    },
    count_conservation: {
      status: 'pass',
      joint: {
        resolved_raw_pairs: {
          total_pairs: 60,
          non_finite_pairs: 0,
          axis_status_matrix: [[0, 0, 0], [0, 60, 0], [0, 0, 0]],
          excluded_pairs: 0,
        },
        rule_screened_pairs: {
          total_pairs: 58,
          non_finite_pairs: 0,
          axis_status_matrix: [[0, 0, 0], [0, 58, 0], [0, 0, 0]],
          excluded_pairs: 2,
        },
      },
      univariate: {
        Suhu: {
          resolved_raw_pairs: { total: 60, finite: 60, non_finite: 0, underflow: 1, in_domain: 58, overflow: 1, excluded_finite: 0 },
          rule_screened_pairs: { total: 58, finite: 58, non_finite: 0, underflow: 0, in_domain: 58, overflow: 0, excluded_finite: 2 },
        },
        RH: {
          resolved_raw_pairs: { total: 60, finite: 60, non_finite: 0, underflow: 1, in_domain: 58, overflow: 1, excluded_finite: 0 },
          rule_screened_pairs: { total: 58, finite: 58, non_finite: 0, underflow: 0, in_domain: 58, overflow: 0, excluded_finite: 2 },
        },
      },
    },
    quality_metrics: {},
  },
} satisfies EdaSectionResponse

const jointResponse = {
  ...section('joint_density'),
  section: 'joint_density',
  payload: {
    edges: { temperature_c: [0, 30, 60], relative_humidity_pct: [0, 50, 100] },
    views: {
      resolved_raw_pairs: { histogram: [[10, 20], [20, 10]] },
      rule_screened_pairs: { histogram: [[10, 19], [19, 10]] },
    },
  },
} satisfies EdaSectionResponse

const rawView = { histogram: [30, 28], ecdf_count: [30, 58], ecdf_fraction: [30 / 58, 1] }
const screenedView = { histogram: [29, 29], ecdf_count: [29, 58], ecdf_fraction: [0.5, 1] }
const univariateResponse = {
  ...section('univariate'),
  section: 'univariate',
  payload: {
    channels: {
      Suhu: {
        unit: '°C',
        edges: [0, 30, 60],
        views: { resolved_raw_pairs: rawView, rule_screened_pairs: screenedView },
      },
      RH: {
        unit: '%',
        edges: [0, 50, 100],
        views: { resolved_raw_pairs: rawView, rule_screened_pairs: screenedView },
      },
    },
  },
} satisfies EdaSectionResponse

const excerptResponse = {
  ...section('quality_excerpt'),
  section: 'quality_excerpt',
  payload: {
    selection_kind: 'both_zero',
    from: '2026-02-01T07:00:00',
    to: '2026-02-01T07:00:06',
    records: [
      {
        timestamp_epoch_s: 1_769_904_000,
        suhu: 0,
        rh: 0,
        non_finite: false,
        disconnected: false,
        zero: true,
        range: true,
        duplicate: false,
        conflicting_duplicate: false,
        stale: false,
        rule_screened: false,
      },
      {
        timestamp_epoch_s: 1_769_904_006,
        suhu: 25,
        rh: 60,
        non_finite: false,
        disconnected: false,
        zero: false,
        range: false,
        duplicate: false,
        conflicting_duplicate: false,
        stale: false,
        rule_screened: true,
      },
    ],
  },
} satisfies EdaSectionResponse

const completeBySection: Record<string, EdaSectionResponse> = {
  quality_overview: qualityResponse,
  joint_density: jointResponse,
  univariate: univariateResponse,
  quality_excerpt: excerptResponse,
}

const notEligibleResponse = {
  ...section('quality_overview'),
  status: 'not_eligible',
  reason_code: 'no_exact_pairs',
  detail: 'Tidak ada pasangan exact pada rentang terpilih.',
  payload_sha256: null,
  payload: null,
} satisfies EdaSectionResponse

const panelCases: readonly [string, ComponentType<PanelProps>][] = [
  ['PairingAuditPanel', PairingAuditPanel],
  ['JointDensityPanel', JointDensityPanel],
  ['UnivariateDiagnosticsPanel', UnivariateDiagnosticsPanel],
  ['QualityExcerptPanel', QualityExcerptPanel],
  ['QualityIntegrityPanel', QualityIntegrityPanel],
]

function renderPanel(Component: ComponentType<PanelProps>, runId: string | null = 'run-quality') {
  return render(
    <ThemeProvider theme={theme}>
      <Component runId={runId} />
    </ThemeProvider>,
  )
}

beforeEach(() => {
  useEdaSectionQueryMock.mockReset()
  useEdaSectionQueryMock.mockReturnValue(loadingState)
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
    clearRect: vi.fn(),
    fillRect: vi.fn(),
    fillStyle: '',
  } as unknown as CanvasRenderingContext2D)
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe.each(panelCases)('%s states', (_name, Component) => {
  it('handles empty selection, loading, API error, and not eligible', () => {
    renderPanel(Component, null)
    expect(screen.getByText('Pilih hasil EDA')).not.toBeNull()
    cleanup()

    renderPanel(Component)
    expect(screen.getByRole('status', { busy: true })).not.toBeNull()
    cleanup()

    useEdaSectionQueryMock.mockReturnValue({
      ...loadingState,
      isError: true,
    })
    renderPanel(Component)
    expect(screen.getAllByText('Data request failed').length).toBeGreaterThanOrEqual(1)
    cleanup()

    useEdaSectionQueryMock.mockReturnValue({
      ...loadingState,
      data: notEligibleResponse,
    })
    renderPanel(Component)
    expect(screen.getByText(/belum memenuhi syarat/i)).not.toBeNull()
  })
})

describe('QUALITY panel family complete state', () => {
  it('renders all authoritative panels from independently selected section responses', () => {
    useEdaSectionQueryMock.mockImplementation((_runId: string | null, sectionName: string) => ({
      ...loadingState,
      data: completeBySection[sectionName],
    }))

    render(
      <ThemeProvider theme={theme}>
        <div>
          <PairingAuditPanel runId="run-quality" />
          <JointDensityPanel runId="run-quality" />
          <UnivariateDiagnosticsPanel runId="run-quality" />
          <QualityExcerptPanel runId="run-quality" />
          <QualityIntegrityPanel runId="run-quality" />
        </div>
      </ThemeProvider>,
    )

    expect(screen.getByRole('heading', { name: 'Audit pairing timestamp' })).not.toBeNull()
    expect(screen.getByText('Konservasi hitungan: PASS')).not.toBeNull()
    expect(screen.getByRole('heading', { name: 'Kepadatan gabungan Suhu–RH' })).not.toBeNull()
    expect(screen.getByRole('img', { name: 'Resolved raw — n=60' })).not.toBeNull()
    expect(screen.getByRole('heading', { name: 'Diagnostik univariat' })).not.toBeNull()
    expect(screen.getByRole('table', { name: 'Audit finite Suhu' })).not.toBeNull()
    expect(screen.getByRole('heading', { name: 'Excerpt kejadian kualitas' })).not.toBeNull()
    expect(screen.getByText(/BUKAN label anomali/)).not.toBeNull()
    expect(screen.getByRole('heading', { name: 'Integritas kualitas' })).not.toBeNull()
    expect(screen.getByRole('table', { name: 'Fate domain Resolved raw' })).not.toBeNull()
    expect(screen.getByText('Gate PASS')).not.toBeNull()
    expectDescribedCharts(8)
    expect(screen.getAllByRole('button', { name: 'Lihat data' })).toHaveLength(3)
    expect(useEdaSectionQueryMock).toHaveBeenCalledWith('run-quality', 'quality_overview')
    expect(useEdaSectionQueryMock).toHaveBeenCalledWith('run-quality', 'joint_density')
    expect(useEdaSectionQueryMock).toHaveBeenCalledWith('run-quality', 'univariate')
    expect(useEdaSectionQueryMock).toHaveBeenCalledWith('run-quality', 'quality_excerpt')
  })
})

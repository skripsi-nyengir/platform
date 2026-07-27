import { darken } from '@mui/material/styles'
import { describe, expect, it } from 'vitest'
import type {
  JointDensityPayload,
  QualityExcerptPayload,
  QualityOverviewPayload,
  UnivariatePayload,
} from '../../contracts/eda'
import { theme } from '../../theme/theme'
import {
  buildDomainFateData,
  buildJointDensityData,
  buildPairingAuditData,
  buildQualityExcerptData,
  buildQualityIntegrityData,
  buildUnivariateData,
  formatFinitePercent,
  jointDensityColor,
} from './edaV3Options'

const exactPairs = 3_460_865
const screenedPairs = 3_405_332
const excludedPairs = 55_533

const qualityOverview = {
  source_audit: {
    row_count: 6_930_000,
    union_timestamps: exactPairs + 300,
    intersection_timestamps: exactPairs,
    missing_idx0_timestamps: 100,
    missing_idx1_timestamps: 200,
    duplicate_group_count: 1_200,
    conflicting_duplicate_pair_count: 75,
    exact_pair_count: exactPairs,
    rule_screened_pair_count: screenedPairs,
    observed_median_positive_delta_at_most_gap: 6,
    gap_above_primary_count: 42,
    cadence_gate: 'pass',
  },
  count_conservation: {
    status: 'pass',
    joint: {
      resolved_raw_pairs: {
        total_pairs: exactPairs,
        non_finite_pairs: 5,
        axis_status_matrix: [
          [1, 2, 3],
          [4, exactPairs - 50, 6],
          [7, 8, 14],
        ],
        excluded_pairs: 0,
      },
      rule_screened_pairs: {
        total_pairs: screenedPairs,
        non_finite_pairs: 0,
        axis_status_matrix: [
          [0, 1, 0],
          [1, screenedPairs - 4, 1],
          [0, 1, 0],
        ],
        excluded_pairs: excludedPairs,
      },
    },
    univariate: {
      Suhu: {
        resolved_raw_pairs: {
          total: exactPairs,
          finite: exactPairs,
          non_finite: 0,
          underflow: 1_000,
          in_domain: exactPairs - 2_000,
          overflow: 1_000,
          excluded_finite: 0,
        },
        rule_screened_pairs: {
          total: screenedPairs,
          finite: screenedPairs,
          non_finite: 0,
          underflow: 0,
          in_domain: screenedPairs,
          overflow: 0,
          excluded_finite: excludedPairs,
        },
      },
      RH: {
        resolved_raw_pairs: {
          total: exactPairs,
          finite: exactPairs,
          non_finite: 0,
          underflow: 500,
          in_domain: exactPairs - 1_000,
          overflow: 500,
          excluded_finite: 0,
        },
        rule_screened_pairs: {
          total: screenedPairs,
          finite: screenedPairs,
          non_finite: 0,
          underflow: 0,
          in_domain: screenedPairs,
          overflow: 0,
          excluded_finite: excludedPairs,
        },
      },
    },
  },
  quality_metrics: {},
} satisfies QualityOverviewPayload

function edges(binCount: number, maximum: number): number[] {
  return Array.from({ length: binCount + 1 }, (_, index) => (index * maximum) / binCount)
}

function univariateView(binCount: number, count: number) {
  return {
    histogram: [count, ...Array.from({ length: binCount - 1 }, () => 0)],
    ecdf_count: Array.from({ length: binCount }, () => count),
    ecdf_fraction: Array.from({ length: binCount }, () => 1),
  }
}

const univariate = {
  channels: {
    Suhu: {
      unit: '°C',
      edges: edges(600, 60),
      views: {
        resolved_raw_pairs: univariateView(600, exactPairs - 2_000),
        rule_screened_pairs: univariateView(600, screenedPairs),
      },
    },
    RH: {
      unit: '%',
      edges: edges(400, 100),
      views: {
        resolved_raw_pairs: univariateView(400, exactPairs - 1_000),
        rule_screened_pairs: univariateView(400, screenedPairs),
      },
    },
  },
} satisfies UnivariatePayload

describe('EDA v3 quality mappers', () => {
  it('maps aligned pairing bars and keeps conservation separate', () => {
    const data = buildPairingAuditData(qualityOverview, theme)

    expect(data?.conservationStatus).toBe('pass')
    expect(data?.bars[0].total).toBe(exactPairs + 300)
    expect(data?.bars[0].segments.map((segment) => segment.count)).toEqual([exactPairs, 100, 200])
    expect(data?.bars[1].segments.map((segment) => segment.count)).toEqual([screenedPairs, excludedPairs])
    expect(data?.bars[1].segments.reduce((sum, segment) => sum + segment.percent, 0)).toBeCloseTo(100)
    expect(data?.bars[1].segments[1].label).toBe('Dikecualikan aturan kualitas')
  })

  it('preserves mandatory joint axes and uses one exact log color scale', () => {
    const raw = Array.from({ length: 120 }, () => Array.from({ length: 200 }, () => 0))
    const screened = Array.from({ length: 120 }, () => Array.from({ length: 200 }, () => 0))
    raw[119][199] = 91
    screened[0][0] = 17
    const payload = {
      edges: { temperature_c: edges(120, 60), relative_humidity_pct: edges(200, 100) },
      views: {
        resolved_raw_pairs: { histogram: raw },
        rule_screened_pairs: { histogram: screened },
      },
    } satisfies JointDensityPayload
    const data = buildJointDensityData(payload, { exact_pairs: exactPairs, screened_pairs: screenedPairs }, theme)

    expect(data?.temperatureEdges).toHaveLength(121)
    expect(data?.humidityEdges).toHaveLength(201)
    expect(data?.views[0].matrix).toHaveLength(120)
    expect(data?.views[0].matrix[0]).toHaveLength(200)
    expect(data?.maximumCount).toBe(91)
    expect(data?.views.map((view) => view.pairCount)).toEqual([exactPairs, screenedPairs])
    expect(jointDensityColor(0, 91, data?.colors ?? [])).toBe(theme.palette.background.default)
    expect(jointDensityColor(91, 91, data?.colors ?? [])).toBe(theme.palette.success.main)
  })

  it('maps 600/400-bin histograms, ECDF axes, audits, and finite denominators', () => {
    const [suhu, rh] = buildUnivariateData(univariate, qualityOverview, theme)

    expect(suhu.edges).toHaveLength(601)
    expect(suhu.centers).toHaveLength(600)
    expect(suhu.ecdfX.at(-1)).toBe(60)
    expect(suhu.views[0].underflow).toBe(1_000)
    expect(suhu.views[0].overflow).toBe(1_000)
    expect(suhu.views[0].finite).toBe(exactPairs)
    expect(suhu.views[0].ecdfDenominator).toBe(exactPairs - 2_000)
    expect(suhu.views[1].color).toBe(theme.palette.success.main)
    expect(rh.edges).toHaveLength(401)
    expect(rh.centers).toHaveLength(400)
    expect(rh.ecdfX.at(-1)).toBe(100)
    expect(rh.views[0].underflow).toBe(500)
    expect(formatFinitePercent(1_000, exactPairs)).toMatch(/^0\.03%$/)
    expect(formatFinitePercent(1, 0)).toBe('—')
  })

  it('maps exact 3x3 domain counts and deterministic table colors', () => {
    const [raw, screened] = buildDomainFateData(qualityOverview, theme)

    expect(raw.cells.map((row) => row.map((cell) => cell.count))).toEqual([
      [1, 2, 3],
      [4, exactPairs - 50, 6],
      [7, 8, 14],
    ])
    expect(raw.cells[1][1].backgroundColor).toBe(darken(theme.palette.primary.main, 0.25))
    expect(screened.cells[0][0].backgroundColor).toBe(darken(theme.palette.success.main, 0.85))
    expect(screened.excludedPairs).toBe(excludedPairs)
  })

  it('keeps duplicate denominators separate and maps the cadence strip exactly', () => {
    const data = buildQualityIntegrityData(qualityOverview)

    expect(data?.duplicateGroups).toEqual({
      count: 1_200,
      denominator: 6_930_000,
      denominatorLabel: 'baris sumber mentah',
    })
    expect(data?.conflictingPairs).toEqual({
      count: 75,
      denominator: exactPairs,
      denominatorLabel: 'pasangan exact',
    })
    expect(data?.cadence).toMatchObject({
      observedMedianSeconds: 6,
      expectedSeconds: 6,
      acceptanceMinimumSeconds: 5,
      acceptanceMaximumSeconds: 7,
      primaryGapSeconds: 30,
      gapCount: 42,
      displayMaximumSeconds: 12,
      expectedPositionPercent: 50,
      observedPositionPercent: 50,
    })
    expect(data?.cadence.acceptanceLeftPercent).toBeCloseTo(41.666_666)
    expect(data?.cadence.acceptanceWidthPercent).toBeCloseTo(16.666_666)
  })

  it('maps Jakarta bounds, gaps, and overlapping excerpt flags without losing rows', () => {
    const payload = {
      selection_kind: 'both_zero',
      from: '2026-02-01T07:00:00',
      to: '2026-02-01T07:00:40',
      records: [
        {
          timestamp_epoch_s: 1_769_904_000,
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
        {
          timestamp_epoch_s: 1_769_904_006,
          suhu: 0,
          rh: 0,
          non_finite: false,
          disconnected: false,
          zero: true,
          range: true,
          duplicate: true,
          conflicting_duplicate: false,
          stale: false,
          rule_screened: false,
        },
        {
          timestamp_epoch_s: 1_769_904_040,
          suhu: 24,
          rh: 59,
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
    } satisfies QualityExcerptPayload
    const data = buildQualityExcerptData(payload, theme)

    expect(data?.from.toISOString()).toBe('2026-02-01T00:00:00.000Z')
    expect(data?.records[1].activeFlags).toEqual(['zero', 'range', 'duplicate'])
    expect(data?.records.at(-1)?.positionPercent).toBe(100)
    expect(data?.temperature.map((point) => point.value)).toEqual([25, 0, null, 24])
    expect(data?.humidity.map((point) => point.value)).toEqual([60, 0, null, 59])
  })
})

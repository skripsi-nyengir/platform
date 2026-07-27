import { describe, expect, it } from 'vitest'
import {
  TemporalCoveragePayloadSchema,
  TemporalDistributionPayloadSchema,
  type TemporalCoveragePayload,
  type TemporalDistributionPayload,
} from '../../contracts/eda'
import {
  buildTemporalCoverageData,
  buildTemporalDistributionData,
  buildWeekdayHourMatrix,
  formatTemporalPercent,
} from './temporalEdaOptions'

interface CoverageBin {
  start: string
  end: string
  exposure_seconds: number
  full_bin_seconds: number
  expected_slots: number
  exact_pair_count: number
  view_pair_count: number
  coverage: number | null
  retention: number | null
  partial: boolean
  from_censored: boolean
  to_censored: boolean
  eligible: { '0.50': boolean; '0.80': boolean; '0.95': boolean }
}

function coverageBin(overrides: Partial<CoverageBin> = {}): CoverageBin {
  return {
    start: '2025-06-23T00:00:00+07:00',
    end: '2025-06-23T01:00:00+07:00',
    exposure_seconds: 3_600,
    full_bin_seconds: 3_600,
    expected_slots: 600,
    exact_pair_count: 600,
    view_pair_count: 600,
    coverage: 1,
    retention: 1,
    partial: false,
    from_censored: false,
    to_censored: false,
    eligible: { '0.50': true, '0.80': true, '0.95': true },
    ...overrides,
  }
}

function coveragePayload(
  raw: CoverageBin[],
  screened: CoverageBin[],
): TemporalCoveragePayload {
  return TemporalCoveragePayloadSchema.parse({
    calendar_semantics: {
      timezone: 'Asia/Jakarta',
      bins: 'half_open',
      empty_bins_explicit: true,
      coverage_not_capped: true,
    },
    views: {
      resolved_raw_pairs: {
        hourly: raw,
        daily: raw,
        monthly: raw,
        dense_regimes: {
          '0.50': [],
          '0.80': [{
            start: '2025-06-01T00:00:00+07:00',
            end: '2025-09-01T00:00:00+07:00',
            months: 3,
          }],
          '0.95': [],
        },
      },
      rule_screened_pairs: {
        hourly: screened,
        daily: screened,
        monthly: screened,
        dense_regimes: { '0.50': [], '0.80': [], '0.95': [] },
      },
    },
  })
}

interface DistributionBin {
  start: string
  end: string
  view_pair_count: number
  from_censored: boolean
  to_censored: boolean
  statistics: {
    count: number
    suhu: { median: number | null; q1: number | null; q3: number | null; mad: number | null }
    rh: { median: number | null; q1: number | null; q3: number | null; mad: number | null }
  }
}

function distributionBin(overrides: Partial<DistributionBin> = {}): DistributionBin {
  return {
    start: '2025-06-23T00:00:00+07:00',
    end: '2025-06-23T01:00:00+07:00',
    view_pair_count: 10,
    from_censored: false,
    to_censored: false,
    statistics: {
      count: 10,
      suhu: { median: 25, q1: 24, q3: 26, mad: 1 },
      rh: { median: 60, q1: 58, q3: 62, mad: 2 },
    },
    ...overrides,
  }
}

function distributionPayload(
  raw: DistributionBin[],
  screened: DistributionBin[],
): TemporalDistributionPayload {
  return TemporalDistributionPayloadSchema.parse({
    cadence: { expected_seconds: 6, publication_gate: 'pass' },
    views: {
      resolved_raw_pairs: {
        hourly: raw,
        daily: raw,
        monthly: raw,
        channels: {
          suhu: { name: 'Suhu', unit: '°C' },
          rh: { name: 'RH', unit: '%' },
        },
        drift_conclusions: {
          suhu: { status: 'robust', directions: { '0.50': 'increase', '0.80': 'increase', '0.95': 'increase' } },
          rh: { status: 'insufficient_data', directions: { '0.50': 'insufficient_data' } },
        },
      },
      rule_screened_pairs: {
        hourly: screened,
        daily: screened,
        monthly: screened,
        channels: {
          suhu: { name: 'Suhu', unit: '°C' },
          rh: { name: 'RH', unit: '%' },
        },
        drift_conclusions: {
          suhu: { status: 'not_robust', directions: { '0.50': 'increase', '0.80': 'stable', '0.95': 'decrease' } },
          rh: { status: 'insufficient_data', directions: { '0.50': 'insufficient_data' } },
        },
      },
    },
  })
}

describe('temporal EDA coverage mapper', () => {
  it('keeps uncapped coverage, explicit zero bins, censor markers, counts, and eligibility', () => {
    const raw = [
      coverageBin({
        expected_slots: 600,
        exact_pair_count: 660,
        view_pair_count: 660,
        coverage: 1.1,
        partial: true,
        from_censored: true,
      }),
      coverageBin({
        start: '2025-06-23T01:00:00+07:00',
        end: '2025-06-23T02:00:00+07:00',
        exact_pair_count: 0,
        view_pair_count: 0,
        coverage: 0,
        retention: null,
        to_censored: true,
        eligible: { '0.50': false, '0.80': false, '0.95': false },
      }),
    ]
    const screened = [
      coverageBin({
        expected_slots: 600,
        exact_pair_count: 660,
        view_pair_count: 600,
        coverage: 1.1,
        retention: 600 / 660,
        partial: true,
        from_censored: true,
      }),
      coverageBin({
        start: '2025-06-23T01:00:00+07:00',
        end: '2025-06-23T02:00:00+07:00',
        exact_pair_count: 0,
        view_pair_count: 0,
        coverage: 0,
        retention: null,
        to_censored: true,
        eligible: { '0.50': false, '0.80': false, '0.95': false },
      }),
    ]

    const result = buildTemporalCoverageData(coveragePayload(raw, screened), 'hourly')

    expect(result.coverage).toEqual([1.1, 0])
    expect(formatTemporalPercent(result.coverage[0])).toBe('110%')
    expect(result.retention).toEqual([600 / 660, null])
    expect(result.partialMarkers).toEqual([1.1, null])
    expect(result.censoredMarkers).toEqual([1.1, 0])
    expect(result.totals).toEqual({
      expectedSlots: 1_200,
      exactPairCount: 660,
      screenedPairCount: 600,
      coverage: 0.55,
      retention: 600 / 660,
    })
    expect(result.eligibility).toEqual({ '0.50': 1, '0.80': 1, '0.95': 1 })
    expect(result.denseRegimes['0.80']).toHaveLength(1)
  })

  it('weights weekday-hour cells from summed counts and slots instead of percentages', () => {
    const firstMonday = coverageBin({
      expected_slots: 100,
      exact_pair_count: 100,
      view_pair_count: 50,
      coverage: 1,
      retention: 0.5,
    })
    const nextMonday = coverageBin({
      start: '2025-06-30T00:00:00+07:00',
      end: '2025-06-30T01:00:00+07:00',
      expected_slots: 900,
      exact_pair_count: 0,
      view_pair_count: 0,
      coverage: 0,
      retention: null,
      eligible: { '0.50': false, '0.80': false, '0.95': false },
    })
    const payload = coveragePayload(
      [firstMonday, nextMonday],
      [firstMonday, nextMonday],
    )

    const result = buildWeekdayHourMatrix(payload, 'rule_screened_pairs')
    const mondayMidnight = result.cells[0]

    expect(mondayMidnight.weekdayLabel).toBe('Senin')
    expect(mondayMidnight.expectedSlots).toBe(1_000)
    expect(mondayMidnight.exactPairCount).toBe(100)
    expect(mondayMidnight.viewPairCount).toBe(50)
    expect(mondayMidnight.coverage).toBe(0.1)
    expect(mondayMidnight.coverage).not.toBe((1 + 0) / 2)
    expect(mondayMidnight.retention).toBe(0.5)
    expect(result.cells).toHaveLength(168)
    expect(result.hasTwoLocalWeeks).toBe(false)
  })
})

describe('temporal EDA distribution mapper', () => {
  it('keeps units separate and breaks all three lines at empty and censored bins', () => {
    const empty = distributionBin({
      start: '2025-06-23T01:00:00+07:00',
      end: '2025-06-23T02:00:00+07:00',
      view_pair_count: 0,
      statistics: {
        count: 0,
        suhu: { median: null, q1: null, q3: null, mad: null },
        rh: { median: null, q1: null, q3: null, mad: null },
      },
    })
    const censored = distributionBin({
      start: '2025-06-23T02:00:00+07:00',
      end: '2025-06-23T03:00:00+07:00',
      from_censored: true,
    })
    const payload = distributionPayload(
      [distributionBin(), empty, censored],
      [distributionBin({
        statistics: {
          count: 8,
          suhu: { median: 23, q1: 22, q3: 24, mad: 0.5 },
          rh: { median: 55, q1: 54, q3: 56, mad: 1 },
        },
      }), empty, censored],
    )

    const raw = buildTemporalDistributionData(payload, 'resolved_raw_pairs', 'hourly')
    const screened = buildTemporalDistributionData(payload, 'rule_screened_pairs', 'hourly')

    expect(raw.channels[0].unit).toBe('°C')
    expect(raw.channels[1].unit).toBe('%')
    expect(raw.channels[0].points.map((point) => point.median)).toEqual([25, null, null])
    expect(raw.channels[0].points.map((point) => point.q1)).toEqual([24, null, null])
    expect(raw.channels[0].points.map((point) => point.q3)).toEqual([26, null, null])
    expect(raw.channels[1].points.map((point) => point.median)).toEqual([60, null, null])
    expect(raw.rows[2]?.censored).toBe(true)
    expect(raw.rows[2]?.suhuMad).toBe(1)
    expect(screened.channels[0].points[0]?.median).toBe(23)
    expect(screened.channels[0].points[0]?.count).toBe(8)
    expect(raw.driftConclusions.suhu?.status).toBe('robust')
    expect(screened.driftConclusions.suhu?.status).toBe('not_robust')
  })
})

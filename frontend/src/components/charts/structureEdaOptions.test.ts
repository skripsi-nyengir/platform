import { describe, expect, it } from 'vitest'
import {
  ChangePointsPayloadSchema,
  StationarityPayloadSchema,
  type ChangePointsPayload,
  type StationarityPayload,
} from '../../contracts/eda'
import {
  AUTOCORRELATION_DOMAIN,
  STL_PERIOD_HOURS,
  buildAutocorrelationData,
  buildChangePointData,
  buildSpectrumData,
  buildStationarityEligibilityData,
  buildStlData,
} from './structureEdaOptions'

type StationaritySegment = StationarityPayload['sensitivity'][number]

function sequence(method: 'acf_fft' | 'pacf_ywm', scale = 1) {
  return {
    status: 'ok' as const,
    method,
    values: Array.from({ length: 73 }, (_, lag) => scale * (1 - lag / 72)),
    maximum_lag: 72,
    error: null,
  }
}

function segment(start: string, hours: 336 | 720): StationaritySegment {
  const hourly = Array.from({ length: hours }, (_, index) => index)
  return {
    status: 'ok',
    start,
    end: new Date(new Date(start).getTime() + hours * 3_600_000).toISOString(),
    hours,
    channels: {
      suhu: {
        autocorrelation: sequence('acf_fft'),
        partial_autocorrelation: sequence('pacf_ywm', 0.5),
        spectrum: {
          status: 'ok',
          frequencies: [0, 1 / 24, 0.5],
          power: [1, 12, 2],
          error: null,
        },
        stl: {
          status: 'ok',
          trend: hourly.map((value) => 20 + value / 100),
          seasonal: hourly.map((value) => value % 24),
          residual: hourly.map(() => 0.1),
          error: null,
        },
      },
      rh: {
        autocorrelation: sequence('acf_fft', 0.8),
        partial_autocorrelation: sequence('pacf_ywm', 0.4),
        spectrum: {
          status: 'ok',
          frequencies: [0, 1 / 12, 0.5],
          power: [2, 20, 3],
          error: null,
        },
        stl: {
          status: 'ok',
          trend: hourly.map((value) => 60 - value / 100),
          seasonal: hourly.map((value) => -(value % 24)),
          residual: hourly.map(() => -0.2),
          error: null,
        },
      },
    },
  }
}

function stationarityPayload(tier: 'sensitivity' | 'primary'): StationarityPayload {
  const sensitivity = segment('2025-07-01T00:00:00+07:00', 336)
  return StationarityPayloadSchema.parse({
    eligibility_tier: tier,
    primary: tier === 'primary' ? segment('2025-08-01T00:00:00+07:00', 720) : null,
    sensitivity: [sensitivity],
  })
}

function changePointsPayload(): ChangePointsPayload {
  return ChangePointsPayloadSchema.parse({
    blocks: [
      {
        status: 'ok',
        pair_count: 100,
        start_day: 20_500,
        end_day: 20_599,
        scale_median: [25, 60],
        scale_mad: [0.5, 2],
        constant_channels: [],
        stable_changes: [
          {
            representative_day: 20_558,
            representative_boundary_index: 58,
            penalty_factors: [1, 2, 4, 8],
            observed_days: [20_559, 20_558, 20_557, 20_558],
            temperature_shift: -0.3,
            humidity_shift: -4,
            temperature_mad_effect: -0.6,
            humidity_mad_effect: -2,
          },
          {
            representative_day: 20_531,
            representative_boundary_index: 31,
            penalty_factors: [1, 2, 4],
            observed_days: [20_532, 20_531, 20_530],
            temperature_shift: 0.4,
            humidity_shift: -3.5,
            temperature_mad_effect: 0.8,
            humidity_mad_effect: -1.75,
          },
        ],
        confirmations: [
          {
            minimum_segment_days: 14,
            status: 'ok',
            requested_breakpoints: 2,
            boundary_days: [20_531, 20_558],
            matched_stable_changes: 2,
            error: null,
          },
          {
            minimum_segment_days: 7,
            status: 'ok',
            requested_breakpoints: 2,
            boundary_days: [20_531, 20_558],
            matched_stable_changes: 2,
            error: null,
          },
          {
            minimum_segment_days: 28,
            status: 'insufficient_data',
            requested_breakpoints: 2,
            boundary_days: [],
            matched_stable_changes: 0,
            error: 'requested breakpoints are infeasible',
          },
        ],
      },
      {
        status: 'constant',
        pair_count: 90,
        start_day: 20_600,
        end_day: 20_689,
        scale_median: [26, 58],
        scale_mad: [0, 0],
        constant_channels: [0, 1],
        stable_changes: [],
        confirmations: [],
      },
    ],
  })
}

describe('stationarity eligibility mapper', () => {
  it.each(['sensitivity', 'primary'] as const)(
    'selects the admitted %s tier without collapsing ADF and KPSS',
    (tier) => {
      const result = buildStationarityEligibilityData(stationarityPayload(tier))

      expect(result.tier).toBe(tier)
      expect(result.selected.kind).toBe(tier)
      expect(result.selected.hours).toBe(tier === 'primary' ? 720 : 336)
      expect(result.aggregation).toBe('Median per jam')
      expect(result.sensitivitySegments).toHaveLength(1)
      expect(result.methodNotice).toContain('hipotesis nol berbeda')
      expect(result).not.toHaveProperty('stationary')
    },
  )
})

describe('stationarity chart mappers', () => {
  const payload = stationarityPayload('primary')

  it('keeps 73 ordered hourly lags and the fixed coefficient domain', () => {
    const result = buildAutocorrelationData(payload)

    expect(AUTOCORRELATION_DOMAIN).toEqual([-1, 1])
    expect(result.channels.map((channel) => channel.key)).toEqual(['suhu', 'rh'])
    for (const channel of result.channels) {
      expect(channel.lags).toEqual(Array.from({ length: 73 }, (_, lag) => lag))
      expect(channel.autocorrelation).toHaveLength(73)
      expect(channel.partialAutocorrelation).toHaveLength(73)
    }
  })

  it('aligns frequency and power and only derives finite nonzero periods', () => {
    const result = buildSpectrumData(payload)

    expect(result.channels[0].rows.map((row) => row.frequency)).toEqual([0, 1 / 24, 0.5])
    expect(result.channels[0].rows.map((row) => row.power)).toEqual([1, 12, 2])
    expect(result.channels[0].rows.map((row) => row.periodHours)).toEqual([null, 24, 2])
    expect(result.channels[1].rows[1]?.periodHours).toBe(12)
  })

  it('uses a fixed 24-hour STL period and aligns all components to hourly timestamps', () => {
    const result = buildStlData(payload)

    expect(STL_PERIOD_HOURS).toBe(24)
    expect(result.periodHours).toBe(24)
    for (const channel of result.channels) {
      expect(channel.rows).toHaveLength(720)
      expect(channel.rows.map((row) => row.trend)).toHaveLength(channel.rows.length)
      expect(channel.rows.map((row) => row.seasonal)).toHaveLength(channel.rows.length)
      expect(channel.rows.map((row) => row.residual)).toHaveLength(channel.rows.length)
      expect(channel.rows[1]?.timestamp.getTime() - channel.rows[0]?.timestamp.getTime()).toBe(3_600_000)
    }
  })

  it('preserves missing spectrum and STL observations instead of fabricating zeroes', () => {
    const misaligned = stationarityPayload('primary')
    if (misaligned.primary === null) throw new Error('Expected primary segment')
    misaligned.primary.channels.suhu.spectrum.power = [0]
    misaligned.primary.channels.suhu.stl.seasonal = [0]
    misaligned.primary.channels.suhu.stl.residual = [0]

    const spectrum = buildSpectrumData(misaligned).channels[0]
    const stl = buildStlData(misaligned).channels[0]

    expect(spectrum.rows[0]?.power).toBe(0)
    expect(spectrum.rows[1]?.power).toBeNull()
    expect(stl.rows[0]?.seasonal).toBe(0)
    expect(stl.rows[0]?.residual).toBe(0)
    expect(stl.rows[1]?.seasonal).toBeNull()
    expect(stl.rows[1]?.residual).toBeNull()
  })
})

describe('change-point mapper', () => {
  it('sorts daily candidates, preserves separate units, and exposes stability without audit details in chart data', () => {
    const result = buildChangePointData(changePointsPayload())

    expect(result.candidates.map((candidate) => candidate.day)).toEqual([20_531, 20_558])
    expect(result.candidates.map((candidate) => candidate.dateLabel)).toEqual(['2026-03-19', '2026-04-15'])
    expect(result.candidates.map((candidate) => candidate.stabilityCount)).toEqual([3, 4])
    expect(result.channels.map((channel) => [channel.key, channel.shiftUnit, channel.effectUnit])).toEqual([
      ['suhu', '°C', 'MAD'],
      ['rh', '%', 'MAD'],
    ])
    expect(result.candidates[0]).not.toHaveProperty('penaltyFactors')
    expect(result.candidates[0]).not.toHaveProperty('confirmations')
    expect(result.candidates[0]).not.toHaveProperty('scaleMedian')
  })

  it('orders minimum-segment confirmations and retains constants and scales only in audit rows', () => {
    const result = buildChangePointData(changePointsPayload())

    expect(result.confirmationSummary.map((item) => item.minimumSegmentDays)).toEqual([7, 14, 28])
    expect(result.confirmationSummary.map((item) => item.matchedStableChanges)).toEqual([2, 2, 0])
    expect(result.auditRows.some((row) => row.constantChannels === 'Suhu, RH')).toBe(true)
    expect(result.auditRows[0]?.scaleMedianSuhu).toBe(25)
    expect(result.auditRows[0]?.penaltyFactors).toBe('1, 2, 4')
  })
})

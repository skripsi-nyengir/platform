import { describe, expect, it } from 'vitest'
import {
  RelationshipsPayloadSchema,
  UncertaintyPayloadSchema,
  type RelationshipsPayload,
  type UncertaintyPayload,
} from '../../contracts/eda'
import {
  buildAssociationSummaryData,
  buildBootstrapForestData,
  buildRollingCorrelationData,
  coefficientDomain,
  rollingVariantKey,
} from './relationshipEdaOptions'

type RollingResult = RelationshipsPayload['rolling_pearson']['resolved_raw_pairs']['window_30m_gap_30s']

function rollingResult(
  windowSeconds: 900 | 1800 | 3600 | 10800,
  gapSeconds: 15 | 30 | 60,
  correlations: number[] = [0.1, 0.2, 0.3],
  timestamps: number[] = [1_000, 1_006, 1_012],
): RollingResult {
  return {
    status: 'complete',
    reason_code: null,
    window_seconds: windowSeconds,
    gap_boundary_seconds: gapSeconds,
    eligible_window_count: correlations.length,
    total_endpoint_count: 300,
    minimum: Math.min(...correlations),
    q05: correlations[0] ?? 0,
    q25: correlations[0] ?? 0,
    median: correlations[Math.floor(correlations.length / 2)] ?? 0,
    q75: correlations.at(-1) ?? 0,
    q95: correlations.at(-1) ?? 0,
    maximum: Math.max(...correlations),
    plotted_end_timestamps: timestamps,
    plotted_correlations: correlations,
  }
}

function rollingVariants(primary = rollingResult(1800, 30)) {
  return {
    window_15m_gap_30s: rollingResult(900, 30),
    window_30m_gap_15s: rollingResult(1800, 15),
    window_30m_gap_30s: primary,
    window_30m_gap_60s: rollingResult(1800, 60),
    window_60m_gap_30s: rollingResult(3600, 30),
    window_180m_gap_30s: rollingResult(10800, 30),
  }
}

function relationships(primary = rollingResult(1800, 30)): RelationshipsPayload {
  return RelationshipsPayloadSchema.parse({
    static: {
      resolved_raw_pairs: { status: 'ok', pair_count: 40, pearson: -0.4, spearman: 0.7 },
      rule_screened_pairs: { status: 'ok', pair_count: 35, pearson: -0.2, spearman: 0.5 },
    },
    rolling_pearson: {
      resolved_raw_pairs: rollingVariants(primary),
      rule_screened_pairs: rollingVariants(primary),
    },
  })
}

function interval(
  statistic: 'pearson' | 'spearman',
  blockDays: 7 | 14 | 28,
  estimate: number,
  lower: number,
  upper: number,
) {
  return {
    statistic,
    block_days: blockDays,
    status: 'ok' as const,
    pair_count: 90,
    run_count: 2,
    replicate_count: 2000 as const,
    estimate,
    lower,
    upper,
  }
}

function uncertainty(): UncertaintyPayload {
  return UncertaintyPayloadSchema.parse({
    method: 'paired_moving_block_bootstrap',
    confidence_level: 0.95,
    seed: 20260724,
    replicates: 2000,
    blocks: {
      '7': { status: 'complete', reason_code: null, intervals: [interval('spearman', 7, 0.4, 0.1, 0.7), interval('pearson', 7, 0.2, -0.1, 0.5)] },
      '14': { status: 'complete', reason_code: null, intervals: [interval('pearson', 14, 0.3, 0.1, 0.6), interval('spearman', 14, 0.5, 0.2, 0.8)] },
      '28': {
        status: 'not_eligible',
        reason_code: 'block_longer_than_run',
        intervals: [
          { ...interval('pearson', 28, 0, 0, 0), status: 'constant', replicate_count: 0, estimate: null, lower: null, upper: null },
          { ...interval('spearman', 28, 0, 0, 0), status: 'constant', replicate_count: 0, estimate: null, lower: null, upper: null },
        ],
      },
    },
    sensitivity_status: 'not_robust',
  })
}

describe('relationship EDA mappers', () => {
  it('keeps the coefficient domain fixed and orders Pearson before Spearman', () => {
    const result = buildAssociationSummaryData(relationships())

    expect(coefficientDomain).toEqual([-1, 1])
    expect(result.map((row) => row.statistic)).toEqual(['pearson', 'spearman'])
    expect(result[0]).toMatchObject({ raw: -0.4, screened: -0.2 })
    expect(result[1]).toMatchObject({ raw: 0.7, screened: 0.5 })
  })

  it('maps only the six published rolling sensitivity variants', () => {
    expect(rollingVariantKey(30, 30)).toBe('window_30m_gap_30s')
    expect(rollingVariantKey(15, 30)).toBe('window_15m_gap_30s')
    expect(rollingVariantKey(30, 15)).toBe('window_30m_gap_15s')
    expect(rollingVariantKey(60, 30)).toBe('window_60m_gap_30s')
    expect(rollingVariantKey(180, 30)).toBe('window_180m_gap_30s')
    expect(rollingVariantKey(15, 15)).toBeNull()
  })

  it('inserts nulls at large timestamp gaps so the rolling line breaks', () => {
    const primary = rollingResult(1800, 30, [0.1, 0.2, -0.3], [1_000, 1_006, 1_100])
    const result = buildRollingCorrelationData(
      relationships(primary),
      'resolved_raw_pairs',
      30,
      30,
    )

    expect(result?.status).toBe('complete')
    expect(result?.rows.map((row) => row.correlation)).toEqual([0.1, 0.2, null, -0.3])
    expect(result?.rows[2]?.gapBreak).toBe(true)
  })

  it('keeps an ineligible rolling result empty instead of creating zeroes', () => {
    const ineligible: RollingResult = {
      ...rollingResult(1800, 30),
      status: 'not_eligible',
      reason_code: 'insufficient_rolling_windows',
      eligible_window_count: 0,
      minimum: null,
      q05: null,
      q25: null,
      median: null,
      q75: null,
      q95: null,
      maximum: null,
      plotted_end_timestamps: [],
      plotted_correlations: [],
    }

    const result = buildRollingCorrelationData(
      relationships(ineligible),
      'rule_screened_pairs',
      30,
      30,
    )

    expect(result).toMatchObject({ status: 'not_eligible', rows: [], reasonCode: 'insufficient_rolling_windows' })
  })

  it('orders forest rows by block and statistic and identifies intervals crossing zero', () => {
    const rows = buildBootstrapForestData(uncertainty())

    expect(rows.map((row) => `${row.blockDays}-${row.statistic}`)).toEqual([
      '7-pearson',
      '7-spearman',
      '14-pearson',
      '14-spearman',
      '28-pearson',
      '28-spearman',
    ])
    expect(rows[0]).toMatchObject({ estimate: 0.2, lower: -0.1, upper: 0.5, crossesZero: true })
    expect(rows[1]?.crossesZero).toBe(false)
  })

  it('does not fabricate estimates or whiskers for constant/not-eligible blocks', () => {
    const rows = buildBootstrapForestData(uncertainty()).filter((row) => row.blockDays === 28)

    expect(rows).toHaveLength(2)
    expect(rows.every((row) => row.blockStatus === 'not_eligible')).toBe(true)
    expect(rows.every((row) => row.intervalStatus === 'constant')).toBe(true)
    expect(rows.every((row) => row.estimate === null && row.lower === null && row.upper === null)).toBe(true)
  })
})

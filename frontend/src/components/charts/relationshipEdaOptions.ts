import type { RelationshipsPayload, UncertaintyPayload } from '../../contracts/eda'

export const coefficientDomain = [-1, 1] as const
export type RelationshipView = keyof RelationshipsPayload['static']
export const relationshipStatistics = ['pearson', 'spearman'] as const
export type RelationshipStatistic = (typeof relationshipStatistics)[number]
export const rollingWindowMinutes = [15, 30, 60, 180] as const
export type RollingWindowMinutes = (typeof rollingWindowMinutes)[number]
export const rollingGapSeconds = [15, 30, 60] as const
export type RollingGapSeconds = (typeof rollingGapSeconds)[number]

type RollingVariants = RelationshipsPayload['rolling_pearson']['resolved_raw_pairs']
export type RollingVariantKey = keyof RollingVariants

export interface AssociationSummaryRow {
  id: RelationshipStatistic
  statistic: RelationshipStatistic
  raw: number
  screened: number
  rawPairCount: number
  screenedPairCount: number
}

export interface RollingCorrelationRow {
  id: string
  timestamp: string
  x: Date
  correlation: number | null
  gapBreak: boolean
}

export interface RollingCorrelationData {
  status: 'complete' | 'not_eligible'
  reasonCode: 'insufficient_rolling_windows' | null
  windowSeconds: number
  gapBoundarySeconds: number
  eligibleWindowCount: number
  totalEndpointCount: number
  minimum: number | null
  median: number | null
  maximum: number | null
  rows: RollingCorrelationRow[]
}

export interface BootstrapForestRow {
  id: string
  blockDays: 7 | 14 | 28
  statistic: RelationshipStatistic
  blockStatus: 'complete' | 'not_eligible'
  intervalStatus: 'ok' | 'insufficient_data' | 'constant'
  reasonCode: 'insufficient_dense_daily_pairs' | 'block_longer_than_run' | null
  pairCount: number
  runCount: number
  replicateCount: 0 | 2000
  estimate: number | null
  lower: number | null
  upper: number | null
  crossesZero: boolean
}

export function formatCoefficient(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return '—'
  return value.toLocaleString('id-ID', { minimumFractionDigits: 2, maximumFractionDigits: 3 })
}

export function buildAssociationSummaryData(
  payload: RelationshipsPayload,
): AssociationSummaryRow[] {
  const raw = payload.static.resolved_raw_pairs
  const screened = payload.static.rule_screened_pairs
  return relationshipStatistics.map((statistic) => ({
    id: statistic,
    statistic,
    raw: raw[statistic],
    screened: screened[statistic],
    rawPairCount: raw.pair_count,
    screenedPairCount: screened.pair_count,
  }))
}

export function rollingVariantKey(
  windowMinutes: RollingWindowMinutes,
  gapSeconds: RollingGapSeconds,
): RollingVariantKey | null {
  if (windowMinutes === 30) return `window_30m_gap_${gapSeconds}s`
  if (gapSeconds !== 30) return null
  return `window_${windowMinutes}m_gap_30s`
}

function rollingRows(
  timestamps: readonly number[],
  correlations: readonly number[],
  gapBoundarySeconds: number,
): RollingCorrelationRow[] {
  if (timestamps.length === 0) return []
  const differences = timestamps
    .slice(1)
    .map((timestamp, index) => timestamp - (timestamps[index] ?? timestamp))
    .filter((difference) => difference > 0)
  const typicalStep = differences.length > 1
    ? Math.min(...differences)
    : gapBoundarySeconds
  const breakThreshold = Math.max(gapBoundarySeconds, typicalStep * 3)

  return timestamps.flatMap((timestamp, index): RollingCorrelationRow[] => {
    const row: RollingCorrelationRow = {
      id: `rolling-${timestamp}-${index}`,
      timestamp: new Date(timestamp * 1_000).toISOString(),
      x: new Date(timestamp * 1_000),
      correlation: correlations[index] ?? null,
      gapBreak: false,
    }
    const previous = timestamps[index - 1]
    if (previous === undefined || timestamp - previous <= breakThreshold) return [row]
    const midpoint = previous + Math.floor((timestamp - previous) / 2)
    return [{
      id: `rolling-gap-${previous}-${timestamp}`,
      timestamp: new Date(midpoint * 1_000).toISOString(),
      x: new Date(midpoint * 1_000),
      correlation: null,
      gapBreak: true,
    }, row]
  })
}

export function buildRollingCorrelationData(
  payload: RelationshipsPayload,
  view: RelationshipView,
  windowMinutes: RollingWindowMinutes,
  gapSeconds: RollingGapSeconds,
): RollingCorrelationData | undefined {
  const key = rollingVariantKey(windowMinutes, gapSeconds)
  if (key === null) return undefined
  const result = payload.rolling_pearson[view][key]
  return {
    status: result.status,
    reasonCode: result.reason_code,
    windowSeconds: result.window_seconds,
    gapBoundarySeconds: result.gap_boundary_seconds,
    eligibleWindowCount: result.eligible_window_count,
    totalEndpointCount: result.total_endpoint_count,
    minimum: result.minimum,
    median: result.median,
    maximum: result.maximum,
    rows: result.status === 'complete'
      ? rollingRows(
          result.plotted_end_timestamps,
          result.plotted_correlations,
          result.gap_boundary_seconds,
        )
      : [],
  }
}

export function buildBootstrapForestData(
  payload: UncertaintyPayload,
): BootstrapForestRow[] {
  return ([7, 14, 28] as const).flatMap((blockDays) => {
    const block = payload.blocks[String(blockDays) as '7' | '14' | '28']
    return relationshipStatistics.map((statistic): BootstrapForestRow => {
      const interval = block.intervals.find((item) => item.statistic === statistic)
      if (interval === undefined) throw new Error(`Missing ${statistic} interval for ${blockDays}-day block`)
      return {
        id: `${blockDays}-${statistic}`,
        blockDays,
        statistic,
        blockStatus: block.status,
        intervalStatus: interval.status,
        reasonCode: block.reason_code,
        pairCount: interval.pair_count,
        runCount: interval.run_count,
        replicateCount: interval.replicate_count,
        estimate: interval.estimate,
        lower: interval.lower,
        upper: interval.upper,
        crossesZero: interval.lower !== null && interval.upper !== null &&
          interval.lower <= 0 && interval.upper >= 0,
      }
    })
  })
}

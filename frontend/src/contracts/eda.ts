import { z } from 'zod'
import {
  HistoricalDateTimeSchema,
  OperationalInstantSchema,
  compareHistoricalDateTimes,
} from './common'

const SOURCE_FROM = '2025-06-23T00:00:00'
const SOURCE_TO = '2026-07-24T09:02:05'
const Sha256Schema = z.string().regex(/^[0-9a-f]{64}$/)
const NonNegativeIntegerSchema = z.number().int().nonnegative()

export const EdaDeviceIdSchema = z.literal('b02f3872-39a2-4b6f-a4ec-045a287fde4b')
export const EdaPeriodKindSchema = z.enum(['daily', 'weekly', 'monthly', 'custom', 'full_range'])
export const EdaPrecomputedPeriodKindSchema = z.enum(['daily', 'weekly', 'monthly'])
export const EdaTriggerKindSchema = z.enum(['api', 'backfill'])
export const EdaJobStatusSchema = z.enum(['queued', 'running', 'succeeded', 'failed'])
export const EdaPanelStatusSchema = z.enum(['complete', 'not_eligible', 'failed'])
export const EdaActiveViewSchema = z.enum(['resolved_raw_pairs', 'rule_screened_pairs'])
export const EdaSectionNameSchema = z.enum([
  'quality_overview',
  'joint_density',
  'univariate',
  'quality_excerpt',
  'temporal_coverage',
  'temporal_distribution',
  'relationships',
  'stationarity',
  'change_points',
  'uncertainty',
  'audit_metadata',
])
export const EdaEligibilityReasonCodeSchema = z.enum([
  'no_exact_pairs',
  'no_selectable_excerpt',
  'no_positive_deltas',
  'insufficient_representative_cadence',
  'no_exposed_calendar_bins',
  'insufficient_nonconstant_pairs',
  'insufficient_rolling_windows',
  'insufficient_stationarity_sensitivity_tier',
  'insufficient_stationarity_primary_tier',
  'insufficient_daily_medians',
  'insufficient_dense_daily_pairs',
  'block_longer_than_run',
  'source_identity_unavailable',
])
export const EdaFailureReasonCodeSchema = z.enum([
  'section_compute_failed',
  'dependency_unavailable',
  'resource_limit_exceeded',
])
export const EdaReasonCodeSchema = z.union([
  EdaEligibilityReasonCodeSchema,
  EdaFailureReasonCodeSchema,
])
export const EdaProvenanceLabelSchema = z.enum([
  'published v3 release',
  'algorithm-equivalent range computation',
])

export type EdaPeriodKind = z.infer<typeof EdaPeriodKindSchema>
export type EdaSectionName = z.infer<typeof EdaSectionNameSchema>
export type EdaPanelStatus = z.infer<typeof EdaPanelStatusSchema>
export type EdaEligibilityReasonCode = z.infer<typeof EdaEligibilityReasonCodeSchema>
export type EdaReasonCode = z.infer<typeof EdaReasonCodeSchema>

const eligibilityReasonsBySection: Record<EdaSectionName, readonly EdaEligibilityReasonCode[]> = {
  quality_overview: ['no_exact_pairs'],
  joint_density: ['no_exact_pairs'],
  univariate: ['no_exact_pairs'],
  quality_excerpt: ['no_exact_pairs', 'no_selectable_excerpt'],
  temporal_coverage: ['no_positive_deltas', 'no_exposed_calendar_bins'],
  temporal_distribution: ['no_positive_deltas', 'insufficient_representative_cadence'],
  relationships: ['no_exact_pairs', 'insufficient_nonconstant_pairs', 'insufficient_rolling_windows'],
  stationarity: [
    'insufficient_stationarity_sensitivity_tier',
    'insufficient_stationarity_primary_tier',
  ],
  change_points: ['insufficient_daily_medians'],
  uncertainty: ['insufficient_dense_daily_pairs', 'block_longer_than_run'],
  audit_metadata: ['source_identity_unavailable'],
}

function localDateTime(value: string): Date {
  return new Date(`${value}Z`)
}

function validateScope(
  value: { period_kind: EdaPeriodKind; from: string; to: string },
  context: z.RefinementCtx,
): void {
  if (compareHistoricalDateTimes(value.from, value.to) >= 0) {
    context.addIssue({ code: 'custom', message: 'from must be earlier than to', path: ['from'] })
    return
  }
  if (value.from < SOURCE_FROM || value.to > SOURCE_TO) {
    context.addIssue({ code: 'custom', message: 'range must be inside the canonical source bounds', path: ['from'] })
    return
  }

  const start = localDateTime(value.from)
  const end = localDateTime(value.to)
  const atMidnight = start.getUTCHours() === 0 && start.getUTCMinutes() === 0 && start.getUTCSeconds() === 0
  if (value.period_kind === 'daily' && (!atMidnight || end.getTime() !== start.getTime() + 86_400_000)) {
    context.addIssue({ code: 'custom', message: 'daily range must be Jakarta [00:00,next day 00:00)', path: ['period_kind'] })
  }
  if (value.period_kind === 'weekly' && (
    !atMidnight || start.getUTCDay() !== 1 || end.getTime() !== start.getTime() + 7 * 86_400_000
  )) {
    context.addIssue({ code: 'custom', message: 'weekly range must be Jakarta [Monday 00:00,next Monday)', path: ['period_kind'] })
  }
  if (value.period_kind === 'monthly') {
    const nextMonth = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth() + 1, 1))
    if (!atMidnight || start.getUTCDate() !== 1 || end.getTime() !== nextMonth.getTime()) {
      context.addIssue({ code: 'custom', message: 'monthly range must be Jakarta calendar-month aligned', path: ['period_kind'] })
    }
  }
  if (value.period_kind === 'full_range' && (value.from !== SOURCE_FROM || value.to !== SOURCE_TO)) {
    context.addIssue({ code: 'custom', message: 'full_range must equal the canonical half-open source range', path: ['period_kind'] })
  }
}

export const EdaScopeSchema = z.strictObject({
  device_id: EdaDeviceIdSchema,
  time_zone: z.literal('Asia/Jakarta'),
  period_kind: EdaPeriodKindSchema,
  from: HistoricalDateTimeSchema,
  to: HistoricalDateTimeSchema,
}).superRefine(validateScope)
export type EdaScope = z.infer<typeof EdaScopeSchema>

export const EdaComputeRequestSchema = EdaScopeSchema.superRefine((value, context) => {
  if (value.period_kind !== 'custom') {
    context.addIssue({ code: 'custom', message: 'compute requests require period_kind=custom', path: ['period_kind'] })
  }
})
export type EdaComputeRequest = z.infer<typeof EdaComputeRequestSchema>

export const EdaPeriodListQuerySchema = z.strictObject({
  period_kind: EdaPrecomputedPeriodKindSchema,
  limit: z.number().int().min(1).max(100).default(25),
  cursor: z.string().regex(/^eda-periods:[0-9]+$/).nullable().default(null),
})
export type EdaPeriodListQuery = z.input<typeof EdaPeriodListQuerySchema>

export const EdaUnitsSchema = z.strictObject({
  temperature: z.literal('°C').default('°C'),
  relative_humidity: z.literal('%').default('%'),
  time: z.literal('second').default('second'),
})

export const EdaSampleCountsSchema = z.strictObject({
  raw_rows: NonNegativeIntegerSchema,
  exact_pairs: NonNegativeIntegerSchema,
  screened_pairs: NonNegativeIntegerSchema,
  active_pairs: NonNegativeIntegerSchema,
}).refine((value) => value.screened_pairs <= value.exact_pairs, {
  message: 'screened_pairs must not exceed exact_pairs',
  path: ['screened_pairs'],
})

export const EdaRangeBoundarySchema = z.strictObject({
  from_censored: z.boolean().default(false),
  to_censored: z.boolean().default(false),
  from_open_ended: z.boolean().default(false),
  to_open_ended: z.boolean().default(false),
})

function validateActivePairCount(
  value: { active_view: z.infer<typeof EdaActiveViewSchema>; sample_counts: z.infer<typeof EdaSampleCountsSchema> },
  context: z.RefinementCtx,
): void {
  const expected = value.active_view === 'resolved_raw_pairs'
    ? value.sample_counts.exact_pairs
    : value.sample_counts.screened_pairs
  if (value.sample_counts.active_pairs !== expected) {
    context.addIssue({ code: 'custom', message: 'active_pairs must match the selected active_view', path: ['sample_counts', 'active_pairs'] })
  }
}

const SectionMetadataCommonShape = {
  run_id: z.string().min(1),
  section: EdaSectionNameSchema,
  detail: z.string().min(1),
  active_view: EdaActiveViewSchema,
  units: EdaUnitsSchema,
  sample_counts: EdaSampleCountsSchema,
  algorithm_version: z.string().min(1),
  config_hash: Sha256Schema,
  source_sha256: Sha256Schema,
  range_boundary: EdaRangeBoundarySchema,
  created_at: OperationalInstantSchema,
}

export const EdaCompleteSectionMetadataSchema = z.strictObject({
  ...SectionMetadataCommonShape,
  status: z.literal('complete'),
  reason_code: z.null(),
  payload_sha256: Sha256Schema,
}).superRefine(validateActivePairCount)
export const EdaNotEligibleSectionMetadataSchema = z.strictObject({
  ...SectionMetadataCommonShape,
  status: z.literal('not_eligible'),
  reason_code: EdaEligibilityReasonCodeSchema,
  payload_sha256: z.null(),
}).superRefine((value, context) => {
  validateActivePairCount(value, context)
  if (!eligibilityReasonsBySection[value.section].includes(value.reason_code)) {
    context.addIssue({ code: 'custom', message: 'eligibility reason is invalid for this section', path: ['reason_code'] })
  }
})
export const EdaFailedSectionMetadataSchema = z.strictObject({
  ...SectionMetadataCommonShape,
  status: z.literal('failed'),
  reason_code: EdaFailureReasonCodeSchema,
  payload_sha256: z.null(),
}).superRefine(validateActivePairCount)
export const EdaSectionMetadataSchema = z.discriminatedUnion('status', [
  EdaCompleteSectionMetadataSchema,
  EdaNotEligibleSectionMetadataSchema,
  EdaFailedSectionMetadataSchema,
])
export type EdaSectionMetadata = z.infer<typeof EdaSectionMetadataSchema>

function payloadKeyIsValid(key: string, dependency = false): boolean {
  if (key.length > 128 || /\p{C}/u.test(key)) return false
  const canonical = [...key.toLocaleLowerCase()]
    .filter((character) => /[\p{L}\p{N}]/u.test(character))
    .join('')
  return !(
    canonical.includes('score') ||
    canonical.includes('candidate') ||
    canonical.includes('threshold') ||
    canonical === 'isanomaly' ||
    (dependency ? canonical.startsWith('model') : canonical.includes('model'))
  )
}

function analyticObjectIsValid(value: unknown, maximumNodeCount = 100_000): boolean {
  let nodeCount = 0
  function visit(item: unknown, depth: number): boolean {
    nodeCount += 1
    if (nodeCount > maximumNodeCount || depth > 20) return false
    if (Array.isArray(item)) {
      return item.length <= 50_000 && item.every((child) => visit(child, depth + 1))
    }
    if (item !== null && typeof item === 'object') {
      const entries = Object.entries(item)
      return entries.length <= 500 && entries.every(
        ([key, child]) => payloadKeyIsValid(key) && visit(child, depth + 1),
      )
    }
    return typeof item !== 'string' || item.length <= 4_096
  }
  return visit(value, 0)
}

export const EdaAnalyticObjectSchema = z.record(z.string(), z.json()).refine(
  (value) => analyticObjectIsValid(value),
  'analytic payload violates field or cardinality limits',
)
const EdaTemporalAnalyticObjectSchema = z.record(z.string(), z.json()).refine(
  (value) => analyticObjectIsValid(value, 500_000),
  'temporal analytic payload violates field or cardinality limits',
)

export const QualityOverviewPayloadSchema = z.strictObject({
  source_audit: EdaAnalyticObjectSchema,
  count_conservation: EdaAnalyticObjectSchema,
  quality_metrics: EdaAnalyticObjectSchema,
})
export const JointDensityPayloadSchema = z.strictObject({
  edges: z.strictObject({
    temperature_c: z.array(z.number()).min(2).max(1_000),
    relative_humidity_pct: z.array(z.number()).min(2).max(1_000),
  }),
  views: z.strictObject({
    resolved_raw_pairs: z.strictObject({ histogram: z.array(z.array(NonNegativeIntegerSchema)).max(1_000) }),
    rule_screened_pairs: z.strictObject({ histogram: z.array(z.array(NonNegativeIntegerSchema)).max(1_000) }),
  }),
}).superRefine((value, context) => {
  for (const [name, edges] of Object.entries(value.edges)) {
    if (edges.some((edge, index) => index > 0 && edges[index - 1] >= edge)) {
      context.addIssue({ code: 'custom', message: 'joint-density edges must be strictly increasing', path: ['edges', name] })
    }
  }
  const rows = value.edges.temperature_c.length - 1
  const columns = value.edges.relative_humidity_pct.length - 1
  for (const [name, view] of Object.entries(value.views)) {
    if (view.histogram.length !== rows || view.histogram.some((row) => row.length !== columns)) {
      context.addIssue({ code: 'custom', message: 'joint-density histogram dimensions must match edges', path: ['views', name, 'histogram'] })
    }
  }
})
const UnivariateViewSchema = z.strictObject({
  histogram: z.array(NonNegativeIntegerSchema).max(1_000),
  ecdf_count: z.array(NonNegativeIntegerSchema).max(50_000),
  ecdf_fraction: z.array(z.number().min(0).max(1)).max(50_000),
}).refine((value) => value.ecdf_count.length === value.ecdf_fraction.length, {
  message: 'ECDF counts and fractions must have equal length',
}).refine((value) => value.ecdf_count.every((item, index) => index === 0 || value.ecdf_count[index - 1] <= item), {
  message: 'ECDF counts must be monotone',
}).refine((value) => value.ecdf_fraction.every((item, index) => index === 0 || value.ecdf_fraction[index - 1] <= item), {
  message: 'ECDF fractions must be monotone',
})
const UnivariateChannelSchema = z.strictObject({
  unit: z.enum(['°C', '%']),
  edges: z.array(z.number()).min(2).max(1_000),
  views: z.strictObject({
    resolved_raw_pairs: UnivariateViewSchema,
    rule_screened_pairs: UnivariateViewSchema,
  }),
}).superRefine((value, context) => {
  if (value.edges.some((edge, index) => index > 0 && value.edges[index - 1] >= edge)) {
    context.addIssue({ code: 'custom', message: 'univariate edges must be strictly increasing', path: ['edges'] })
  }
  for (const [name, view] of Object.entries(value.views)) {
    if (view.histogram.length !== value.edges.length - 1) {
      context.addIssue({ code: 'custom', message: 'univariate histogram length must match edges', path: ['views', name, 'histogram'] })
    }
  }
})
export const UnivariatePayloadSchema = z.strictObject({
  channels: z.strictObject({
    Suhu: UnivariateChannelSchema.refine((value) => value.unit === '°C'),
    RH: UnivariateChannelSchema.refine((value) => value.unit === '%'),
  }),
})
export const QualityExcerptPayloadSchema = z.strictObject({
  selection_kind: z.string().min(1),
  from: HistoricalDateTimeSchema,
  to: HistoricalDateTimeSchema,
  records: z.array(EdaAnalyticObjectSchema).min(1).max(2_000),
}).refine((value) => value.from <= value.to, { message: 'excerpt from must not be later than to', path: ['from'] })
export const TemporalCoveragePayloadSchema = z.strictObject({
  calendar_semantics: EdaAnalyticObjectSchema,
  views: EdaTemporalAnalyticObjectSchema,
})
export const TemporalDistributionPayloadSchema = z.strictObject({
  cadence: EdaAnalyticObjectSchema,
  views: EdaTemporalAnalyticObjectSchema,
})
const CorrelationCoefficientSchema = z.number().min(-1).max(1)
const RelationshipCorrelationSchema = z.strictObject({
  status: z.literal('ok'),
  pair_count: z.number().int().min(30),
  pearson: CorrelationCoefficientSchema,
  spearman: CorrelationCoefficientSchema,
})
const RollingPearsonResultSchema = z.strictObject({
  status: z.enum(['complete', 'not_eligible']),
  reason_code: z.literal('insufficient_rolling_windows').nullable(),
  window_seconds: z.union([z.literal(900), z.literal(1800), z.literal(3600), z.literal(10800)]),
  gap_boundary_seconds: z.union([z.literal(15), z.literal(30), z.literal(60)]),
  eligible_window_count: NonNegativeIntegerSchema,
  total_endpoint_count: NonNegativeIntegerSchema,
  minimum: CorrelationCoefficientSchema.nullable(),
  q05: CorrelationCoefficientSchema.nullable(),
  q25: CorrelationCoefficientSchema.nullable(),
  median: CorrelationCoefficientSchema.nullable(),
  q75: CorrelationCoefficientSchema.nullable(),
  q95: CorrelationCoefficientSchema.nullable(),
  maximum: CorrelationCoefficientSchema.nullable(),
  plotted_end_timestamps: z.array(z.number().int()).max(2_000),
  plotted_correlations: z.array(CorrelationCoefficientSchema).max(2_000),
}).superRefine((value, context) => {
  const summaries = [value.minimum, value.q05, value.q25, value.median, value.q75, value.q95, value.maximum]
  if (value.plotted_end_timestamps.length !== value.plotted_correlations.length) {
    context.addIssue({ code: 'custom', message: 'rolling timestamps and correlations must align', path: ['plotted_correlations'] })
  }
  if (value.plotted_end_timestamps.some((item, index) => index > 0 && value.plotted_end_timestamps[index - 1] >= item)) {
    context.addIssue({ code: 'custom', message: 'rolling timestamps must be strictly increasing', path: ['plotted_end_timestamps'] })
  }
  if (value.status === 'complete' && (
    value.reason_code !== null || value.eligible_window_count === 0 || summaries.some((item) => item === null)
  )) {
    context.addIssue({ code: 'custom', message: 'complete rolling results require finite summaries', path: ['status'] })
  }
  if (value.status === 'not_eligible' && (
    value.reason_code !== 'insufficient_rolling_windows' || value.eligible_window_count !== 0 ||
    summaries.some((item) => item !== null) || value.plotted_end_timestamps.length > 0 || value.plotted_correlations.length > 0
  )) {
    context.addIssue({ code: 'custom', message: 'ineligible rolling results must be empty', path: ['status'] })
  }
})
const RollingVariantsSchema = z.strictObject({
  window_15m_gap_30s: RollingPearsonResultSchema,
  window_30m_gap_15s: RollingPearsonResultSchema,
  window_30m_gap_30s: RollingPearsonResultSchema,
  window_30m_gap_60s: RollingPearsonResultSchema,
  window_60m_gap_30s: RollingPearsonResultSchema,
  window_180m_gap_30s: RollingPearsonResultSchema,
})
export const RelationshipsPayloadSchema = z.strictObject({
  static: z.strictObject({
    resolved_raw_pairs: RelationshipCorrelationSchema,
    rule_screened_pairs: RelationshipCorrelationSchema,
  }),
  rolling_pearson: z.strictObject({
    resolved_raw_pairs: RollingVariantsSchema,
    rule_screened_pairs: RollingVariantsSchema,
  }),
})
const SequenceDiagnosticSchema = z.strictObject({
  status: z.enum(['ok', 'short', 'constant', 'nonfinite', 'error']),
  method: z.enum(['acf_fft', 'pacf_ywm']),
  values: z.array(CorrelationCoefficientSchema).max(73),
  maximum_lag: z.number().int().min(0).max(72),
  error: z.string().nullable(),
}).superRefine((value, context) => {
  if (value.status === 'ok' && value.values.length !== value.maximum_lag + 1) {
    context.addIssue({ code: 'custom', message: 'successful correlation sequence must include lag zero', path: ['values'] })
  }
  if (value.status !== 'ok' && value.values.length > 0) {
    context.addIssue({ code: 'custom', message: 'unsuccessful correlation sequence must be empty', path: ['values'] })
  }
})
const SpectrumDiagnosticSchema = z.strictObject({
  status: z.enum(['ok', 'short', 'constant', 'nonfinite', 'error']),
  frequencies: z.array(z.number()).max(50_000),
  power: z.array(z.number().nonnegative()).max(50_000),
  error: z.string().nullable(),
}).superRefine((value, context) => {
  if (value.frequencies.length !== value.power.length) {
    context.addIssue({ code: 'custom', message: 'spectrum frequency and power arrays must align', path: ['power'] })
  }
  if (value.status === 'ok' && value.frequencies.length === 0) {
    context.addIssue({ code: 'custom', message: 'successful spectrum must contain values', path: ['frequencies'] })
  }
  if (value.status !== 'ok' && (value.frequencies.length > 0 || value.power.length > 0)) {
    context.addIssue({ code: 'custom', message: 'unsuccessful spectrum must be empty', path: ['frequencies'] })
  }
})
const STLDiagnosticSchema = z.strictObject({
  status: z.enum(['ok', 'short', 'constant', 'nonfinite', 'error']),
  seasonal: z.array(z.number()).max(50_000),
  trend: z.array(z.number()).max(50_000),
  residual: z.array(z.number()).max(50_000),
  error: z.string().nullable(),
}).superRefine((value, context) => {
  if (new Set([value.seasonal.length, value.trend.length, value.residual.length]).size !== 1) {
    context.addIssue({ code: 'custom', message: 'STL arrays must align', path: ['seasonal'] })
  }
  if (value.status === 'ok' && value.seasonal.length === 0) {
    context.addIssue({ code: 'custom', message: 'successful STL must contain values', path: ['seasonal'] })
  }
  if (value.status !== 'ok' && value.seasonal.length > 0) {
    context.addIssue({ code: 'custom', message: 'unsuccessful STL must be empty', path: ['seasonal'] })
  }
})
const StationarityChannelSchema = z.strictObject({
  autocorrelation: SequenceDiagnosticSchema,
  partial_autocorrelation: SequenceDiagnosticSchema,
  spectrum: SpectrumDiagnosticSchema,
  stl: STLDiagnosticSchema,
})
const StationaritySegmentSchema = z.strictObject({
  status: z.literal('ok'),
  start: z.string().min(1),
  end: z.string().min(1),
  hours: z.number().int().min(336),
  channels: z.strictObject({ suhu: StationarityChannelSchema, rh: StationarityChannelSchema }),
}).superRefine((value, context) => {
  for (const [channel, diagnostic] of Object.entries(value.channels)) {
    if (diagnostic.stl.status === 'ok' && diagnostic.stl.seasonal.length !== value.hours) {
      context.addIssue({ code: 'custom', message: 'STL arrays must match segment hours', path: ['channels', channel, 'stl'] })
    }
  }
})
export const StationarityPayloadSchema = z.strictObject({
  eligibility_tier: z.enum(['sensitivity', 'primary']),
  primary: StationaritySegmentSchema.nullable(),
  sensitivity: z.array(StationaritySegmentSchema).min(1).max(3),
}).superRefine((value, context) => {
  if (value.eligibility_tier === 'primary' && (value.primary === null || value.primary.hours < 720)) {
    context.addIssue({ code: 'custom', message: 'primary eligibility tier requires 720 hourly medians', path: ['primary'] })
  }
  if (value.eligibility_tier === 'sensitivity' && value.primary !== null) {
    context.addIssue({ code: 'custom', message: 'sensitivity eligibility tier must not include primary results', path: ['primary'] })
  }
})
const StableChangePayloadSchema = z.strictObject({
  representative_day: z.number().int(),
  representative_boundary_index: z.number().int().positive(),
  penalty_factors: z.array(z.union([z.literal(1), z.literal(2), z.literal(4), z.literal(8)])).min(3).max(4),
  observed_days: z.array(z.number().int()).min(3).max(4),
  temperature_shift: z.number(),
  humidity_shift: z.number(),
  temperature_mad_effect: z.number().nullable(),
  humidity_mad_effect: z.number().nullable(),
})
const ChangeConfirmationPayloadSchema = z.strictObject({
  minimum_segment_days: z.union([z.literal(7), z.literal(14), z.literal(28)]),
  status: z.enum(['ok', 'insufficient_data', 'error']),
  requested_breakpoints: NonNegativeIntegerSchema,
  boundary_days: z.array(z.number().int()).max(500),
  matched_stable_changes: NonNegativeIntegerSchema,
  error: z.string().nullable(),
})
const ChangePointBlockPayloadSchema = z.strictObject({
  status: z.enum(['ok', 'constant', 'insufficient_data']),
  pair_count: NonNegativeIntegerSchema,
  start_day: z.number().int(),
  end_day: z.number().int(),
  scale_median: z.tuple([z.number(), z.number()]).nullable(),
  scale_mad: z.tuple([z.number().nonnegative(), z.number().nonnegative()]).nullable(),
  constant_channels: z.array(z.union([z.literal(0), z.literal(1)])).max(2),
  stable_changes: z.array(StableChangePayloadSchema).max(500),
  confirmations: z.array(ChangeConfirmationPayloadSchema).max(3),
}).superRefine((value, context) => {
  if (value.start_day > value.end_day) {
    context.addIssue({ code: 'custom', message: 'change-point block range is invalid', path: ['start_day'] })
  }
  if (value.status === 'insufficient_data' && value.pair_count >= 90) {
    context.addIssue({ code: 'custom', message: 'ineligible change-point blocks must be shorter than 90 days', path: ['pair_count'] })
  }
  if (value.status !== 'insufficient_data' && (
    value.pair_count < 90 || value.scale_median === null || value.scale_mad === null
  )) {
    context.addIssue({ code: 'custom', message: 'eligible change-point blocks require robust scales', path: ['pair_count'] })
  }
})
export const ChangePointsPayloadSchema = z.strictObject({
  blocks: z.array(ChangePointBlockPayloadSchema).min(1).max(500),
})
const BootstrapIntervalPayloadSchema = z.strictObject({
  statistic: z.enum(['pearson', 'spearman']),
  block_days: z.union([z.literal(7), z.literal(14), z.literal(28)]),
  status: z.enum(['ok', 'insufficient_data', 'constant']),
  pair_count: NonNegativeIntegerSchema,
  run_count: NonNegativeIntegerSchema,
  replicate_count: z.union([z.literal(0), z.literal(2000)]),
  estimate: CorrelationCoefficientSchema.nullable(),
  lower: CorrelationCoefficientSchema.nullable(),
  upper: CorrelationCoefficientSchema.nullable(),
}).superRefine((value, context) => {
  const estimates = [value.estimate, value.lower, value.upper]
  if (value.status === 'ok' && (value.replicate_count !== 2_000 || estimates.some((item) => item === null))) {
    context.addIssue({ code: 'custom', message: 'complete bootstrap intervals require 2000 replicates', path: ['replicate_count'] })
  }
  if (value.status !== 'ok' && (value.replicate_count !== 0 || estimates.some((item) => item !== null))) {
    context.addIssue({ code: 'custom', message: 'ineligible bootstrap intervals must not publish estimates', path: ['replicate_count'] })
  }
})
const BootstrapBlockPayloadSchema = z.strictObject({
  status: z.enum(['complete', 'not_eligible']),
  reason_code: z.enum(['insufficient_dense_daily_pairs', 'block_longer_than_run']).nullable(),
  intervals: z.array(BootstrapIntervalPayloadSchema).length(2),
}).superRefine((value, context) => {
  if (new Set(value.intervals.map((item) => item.statistic)).size !== 2) {
    context.addIssue({ code: 'custom', message: 'bootstrap block must contain Pearson and Spearman intervals', path: ['intervals'] })
  }
  if (new Set(value.intervals.map((item) => item.block_days)).size !== 1) {
    context.addIssue({ code: 'custom', message: 'bootstrap intervals must use one block length', path: ['intervals'] })
  }
  if (value.status === 'complete' && (value.reason_code !== null || value.intervals.some((item) => item.status !== 'ok'))) {
    context.addIssue({ code: 'custom', message: 'complete bootstrap blocks require eligible intervals', path: ['status'] })
  }
  if (value.status === 'not_eligible' && (value.reason_code === null || value.intervals.some((item) => item.status === 'ok'))) {
    context.addIssue({ code: 'custom', message: 'ineligible bootstrap blocks require a reason', path: ['status'] })
  }
})
export const UncertaintyPayloadSchema = z.strictObject({
  method: z.literal('paired_moving_block_bootstrap'),
  confidence_level: z.literal(0.95),
  seed: z.literal(20260724),
  replicates: z.literal(2000),
  blocks: z.strictObject({
    '7': BootstrapBlockPayloadSchema,
    '14': BootstrapBlockPayloadSchema,
    '28': BootstrapBlockPayloadSchema,
  }),
  sensitivity_status: z.enum(['robust', 'not_robust', 'insufficient_data']),
}).superRefine((value, context) => {
  for (const [key, block] of Object.entries(value.blocks)) {
    if (block.intervals.some((interval) => interval.block_days !== Number(key))) {
      context.addIssue({ code: 'custom', message: 'bootstrap block keys must match interval lengths', path: ['blocks', key] })
    }
  }
  if (value.blocks['14'].status !== 'complete') {
    context.addIssue({ code: 'custom', message: 'complete uncertainty payload requires the primary 14-day block', path: ['blocks', '14'] })
  }
})
export const AuditMetadataPayloadSchema = z.strictObject({
  dataset_id: z.literal('bivariate_b02f3872_v1'),
  source_manifest_sha256: Sha256Schema,
  release_id: z.literal('bivariate_b02f3872_eda_v3'),
  seed: z.literal(20260724),
  dependencies: z.record(z.string(), z.string().min(1).max(200)).refine(
    (value) => Object.keys(value).length <= 100 && Object.keys(value).every((key) => payloadKeyIsValid(key, true)),
  ),
})

export type QualityOverviewPayload = z.infer<typeof QualityOverviewPayloadSchema>
export type JointDensityPayload = z.infer<typeof JointDensityPayloadSchema>
export type UnivariatePayload = z.infer<typeof UnivariatePayloadSchema>
export type QualityExcerptPayload = z.infer<typeof QualityExcerptPayloadSchema>
export type TemporalCoveragePayload = z.infer<typeof TemporalCoveragePayloadSchema>
export type TemporalDistributionPayload = z.infer<typeof TemporalDistributionPayloadSchema>
export type RelationshipsPayload = z.infer<typeof RelationshipsPayloadSchema>
export type StationarityPayload = z.infer<typeof StationarityPayloadSchema>
export type ChangePointsPayload = z.infer<typeof ChangePointsPayloadSchema>
export type UncertaintyPayload = z.infer<typeof UncertaintyPayloadSchema>
export type AuditMetadataPayload = z.infer<typeof AuditMetadataPayloadSchema>

const CompleteSectionBaseShape = {
  ...SectionMetadataCommonShape,
  status: z.literal('complete'),
  reason_code: z.null(),
  payload_sha256: Sha256Schema,
}
export const EdaCompleteSectionSchema = z.discriminatedUnion('section', [
  z.strictObject({ ...CompleteSectionBaseShape, section: z.literal('quality_overview'), payload: QualityOverviewPayloadSchema }),
  z.strictObject({ ...CompleteSectionBaseShape, section: z.literal('joint_density'), payload: JointDensityPayloadSchema }),
  z.strictObject({ ...CompleteSectionBaseShape, section: z.literal('univariate'), payload: UnivariatePayloadSchema }),
  z.strictObject({ ...CompleteSectionBaseShape, section: z.literal('quality_excerpt'), payload: QualityExcerptPayloadSchema }),
  z.strictObject({ ...CompleteSectionBaseShape, section: z.literal('temporal_coverage'), payload: TemporalCoveragePayloadSchema }),
  z.strictObject({ ...CompleteSectionBaseShape, section: z.literal('temporal_distribution'), payload: TemporalDistributionPayloadSchema }),
  z.strictObject({ ...CompleteSectionBaseShape, section: z.literal('relationships'), payload: RelationshipsPayloadSchema }),
  z.strictObject({ ...CompleteSectionBaseShape, section: z.literal('stationarity'), payload: StationarityPayloadSchema }),
  z.strictObject({ ...CompleteSectionBaseShape, section: z.literal('change_points'), payload: ChangePointsPayloadSchema }),
  z.strictObject({ ...CompleteSectionBaseShape, section: z.literal('uncertainty'), payload: UncertaintyPayloadSchema }),
  z.strictObject({ ...CompleteSectionBaseShape, section: z.literal('audit_metadata'), payload: AuditMetadataPayloadSchema }),
]).superRefine(validateActivePairCount)
export const EdaNotEligibleSectionSchema = z.strictObject({
  ...SectionMetadataCommonShape,
  status: z.literal('not_eligible'),
  reason_code: EdaEligibilityReasonCodeSchema,
  payload_sha256: z.null(),
  payload: z.null(),
}).superRefine((value, context) => {
  validateActivePairCount(value, context)
  if (!eligibilityReasonsBySection[value.section].includes(value.reason_code)) {
    context.addIssue({ code: 'custom', message: 'eligibility reason is invalid for this section', path: ['reason_code'] })
  }
})
export const EdaFailedSectionSchema = z.strictObject({
  ...SectionMetadataCommonShape,
  status: z.literal('failed'),
  reason_code: EdaFailureReasonCodeSchema,
  payload_sha256: z.null(),
  payload: z.null(),
}).superRefine(validateActivePairCount)
export const EdaSectionResponseSchema = z.discriminatedUnion('status', [
  EdaCompleteSectionSchema,
  EdaNotEligibleSectionSchema,
  EdaFailedSectionSchema,
])
export type EdaCompleteSection = z.infer<typeof EdaCompleteSectionSchema>
export type EdaSectionResponse = z.infer<typeof EdaSectionResponseSchema>

export const EdaJobSummarySchema = z.strictObject({
  job_id: z.string().min(1),
  logical_key: Sha256Schema,
  scope: EdaScopeSchema,
  source_sha256: Sha256Schema,
  algorithm_version: z.string().min(1),
  config_hash: Sha256Schema,
  status: EdaJobStatusSchema,
  trigger_kind: EdaTriggerKindSchema,
  attempt_count: NonNegativeIntegerSchema,
  max_attempts: z.number().int().positive(),
  terminal: z.boolean(),
  created_at: OperationalInstantSchema,
  started_at: OperationalInstantSchema.nullable(),
  completed_at: OperationalInstantSchema.nullable(),
  run_id: z.string().nullable(),
  error_code: z.string().min(1).max(128).nullable(),
  error_detail: z.string().min(1).max(2_000).nullable(),
}).superRefine((value, context) => {
  if (value.attempt_count > value.max_attempts) {
    context.addIssue({ code: 'custom', message: 'attempt_count must not exceed max_attempts', path: ['attempt_count'] })
  }
  if (value.status !== 'queued' && value.attempt_count === 0) {
    context.addIssue({ code: 'custom', message: 'started or terminal jobs require at least one attempt', path: ['attempt_count'] })
  }
  if (value.terminal !== ['succeeded', 'failed'].includes(value.status)) {
    context.addIssue({ code: 'custom', message: 'terminal must match job status', path: ['terminal'] })
  }
  const created = Date.parse(value.created_at)
  const started = value.started_at === null ? null : Date.parse(value.started_at)
  const completed = value.completed_at === null ? null : Date.parse(value.completed_at)
  if (started !== null && started < created) {
    context.addIssue({ code: 'custom', message: 'started_at must not precede created_at', path: ['started_at'] })
  }
  if (completed !== null && completed < (started ?? created)) {
    context.addIssue({ code: 'custom', message: 'completed_at must not precede job execution', path: ['completed_at'] })
  }
  if (value.status === 'queued' && [value.started_at, value.completed_at, value.run_id].some((item) => item !== null)) {
    context.addIssue({ code: 'custom', message: 'queued jobs must not have execution or run timestamps', path: ['status'] })
  }
  if (value.status === 'running' && (value.started_at === null || value.completed_at !== null || value.run_id !== null)) {
    context.addIssue({ code: 'custom', message: 'running jobs require only started_at', path: ['status'] })
  }
  if (value.status === 'succeeded' && (
    value.started_at === null || value.completed_at === null || value.run_id === null ||
    value.error_code !== null || value.error_detail !== null
  )) {
    context.addIssue({ code: 'custom', message: 'succeeded jobs require a run and no error', path: ['status'] })
  }
  if (value.status === 'failed' && (
    value.completed_at === null || value.run_id !== null || !value.error_code || !value.error_detail
  )) {
    context.addIssue({ code: 'custom', message: 'failed jobs require a terminal error and no run', path: ['status'] })
  }
  if (['queued', 'running'].includes(value.status) && (value.error_code !== null || value.error_detail !== null)) {
    context.addIssue({ code: 'custom', message: 'active jobs must not expose terminal errors', path: ['status'] })
  }
})
export type EdaJobSummary = z.infer<typeof EdaJobSummarySchema>

export const EdaRunSummarySchema = z.strictObject({
  run_id: z.string().min(1),
  logical_key: Sha256Schema,
  scope: EdaScopeSchema,
  source_sha256: Sha256Schema,
  algorithm_version: z.string().min(1),
  config_hash: Sha256Schema,
  provenance_label: EdaProvenanceLabelSchema,
  canonical_release: z.boolean(),
  completed_at: OperationalInstantSchema,
  sections: z.array(EdaSectionMetadataSchema).length(11),
}).superRefine((value, context) => {
  const expectedLabel = value.canonical_release
    ? 'published v3 release'
    : 'algorithm-equivalent range computation'
  if (value.provenance_label !== expectedLabel) {
    context.addIssue({ code: 'custom', message: 'provenance label must match canonical_release', path: ['provenance_label'] })
  }
  if (value.canonical_release && value.scope.period_kind !== 'full_range') {
    context.addIssue({ code: 'custom', message: 'canonical_release requires full_range', path: ['canonical_release'] })
  }
  const names = value.sections.map((section) => section.section)
  if (new Set(names).size !== 11 || EdaSectionNameSchema.options.some((name) => !names.includes(name))) {
    context.addIssue({ code: 'custom', message: 'run must contain metadata for all eleven sections exactly once', path: ['sections'] })
  }
  if (value.sections.some((section) => section.run_id !== value.run_id)) {
    context.addIssue({ code: 'custom', message: 'section metadata must belong to this run', path: ['sections'] })
  }
  if (value.sections.some((section) =>
    section.source_sha256 !== value.source_sha256 ||
    section.config_hash !== value.config_hash ||
    section.algorithm_version !== value.algorithm_version
  )) {
    context.addIssue({ code: 'custom', message: 'section identity must match the enclosing run', path: ['sections'] })
  }
})
export type EdaRunSummary = z.infer<typeof EdaRunSummarySchema>

export const EdaPeriodListResponseSchema = z.strictObject({
  request_id: z.string().min(1),
  period_kind: EdaPrecomputedPeriodKindSchema,
  items: z.array(EdaRunSummarySchema).max(100),
  next_cursor: z.string().regex(/^eda-periods:[0-9]+$/).nullable(),
  returned_count: NonNegativeIntegerSchema,
}).superRefine((value, context) => {
  if (value.returned_count !== value.items.length) {
    context.addIssue({ code: 'custom', message: 'returned_count must equal items length', path: ['returned_count'] })
  }
  if (value.items.some((item) => item.scope.period_kind !== value.period_kind)) {
    context.addIssue({ code: 'custom', message: 'listed runs must match period_kind', path: ['items'] })
  }
})
export type EdaPeriodListResponse = z.infer<typeof EdaPeriodListResponseSchema>

export const EdaJobResponseSchema = z.strictObject({ request_id: z.string().min(1), job: EdaJobSummarySchema })
export const EdaRunResponseSchema = z.strictObject({ request_id: z.string().min(1), run: EdaRunSummarySchema })
export const EdaComputeResponseSchema = z.discriminatedUnion('cache_hit', [
  z.strictObject({ request_id: z.string().min(1), cache_hit: z.literal(true), run: EdaRunSummarySchema }),
  z.strictObject({ request_id: z.string().min(1), cache_hit: z.literal(false), job: EdaJobSummarySchema }),
])
export type EdaJobResponse = z.infer<typeof EdaJobResponseSchema>
export type EdaRunResponse = z.infer<typeof EdaRunResponseSchema>
export type EdaComputeResponse = z.infer<typeof EdaComputeResponseSchema>

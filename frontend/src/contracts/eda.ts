import { z } from 'zod'
import { BucketSchema, Rfc3339Schema, SensorIdSchema } from './common'

export const EdaFieldSchema = z.enum(['temperature_c', 'relative_humidity_pct', 'score'])
export type EdaField = z.infer<typeof EdaFieldSchema>

export const EdaSummaryQuerySchema = z
  .strictObject({
    deviceId: SensorIdSchema.optional(),
    from: Rfc3339Schema,
    to: Rfc3339Schema,
    bucket: BucketSchema.default('raw'),
  })
  .refine((value) => Date.parse(value.from) < Date.parse(value.to), {
    message: 'from must be earlier than to',
    path: ['from'],
  })
export type EdaSummaryQuery = z.input<typeof EdaSummaryQuerySchema>

export const EdaScopeSchema = z
  .strictObject({
    device_ids: z.array(SensorIdSchema).max(6),
    from: Rfc3339Schema,
    to: Rfc3339Schema,
    bucket: BucketSchema,
  })
  .refine((value) => Date.parse(value.from) < Date.parse(value.to), {
    message: 'from must be earlier than to',
    path: ['from'],
  })
export type EdaScope = z.infer<typeof EdaScopeSchema>

export const CoverageSummarySchema = z.strictObject({
  expected_count: z.number().int().nonnegative(),
  observed_count: z.number().int().nonnegative(),
  coverage_pct: z.number().min(0).max(100),
  gap_count: z.number().int().nonnegative(),
})
export type CoverageSummary = z.infer<typeof CoverageSummarySchema>

export const MissingnessSummarySchema = z.strictObject({
  field: EdaFieldSchema,
  missing_count: z.number().int().nonnegative(),
  missing_pct: z.number().min(0).max(100),
})
export type MissingnessSummary = z.infer<typeof MissingnessSummarySchema>

export const PercentileSummarySchema = z.strictObject({
  mean: z.number(),
  p05: z.number(),
  p95: z.number(),
})
export type PercentileSummary = z.infer<typeof PercentileSummarySchema>

export const SensorComparisonSchema = z.strictObject({
  device_id: SensorIdSchema,
  sample_count: z.number().int().nonnegative(),
  coverage_pct: z.number().min(0).max(100),
  temperature_c: PercentileSummarySchema,
  relative_humidity_pct: PercentileSummarySchema,
})
export type SensorComparison = z.infer<typeof SensorComparisonSchema>

export const CandidateOutlierSchema = z
  .strictObject({
    device_id: SensorIdSchema,
    start_ts: Rfc3339Schema,
    end_ts: Rfc3339Schema,
    reason: z.string(),
    score: z.number(),
  })
  .refine((value) => Date.parse(value.start_ts) <= Date.parse(value.end_ts), {
    message: 'start_ts must not be later than end_ts',
    path: ['start_ts'],
  })
export type CandidateOutlier = z.infer<typeof CandidateOutlierSchema>

export const EdaSummaryResponseSchema = z.strictObject({
  request_id: z.string(),
  scope: EdaScopeSchema,
  coverage: CoverageSummarySchema,
  missingness: z.array(MissingnessSummarySchema).max(3),
  sensor_comparison: z.array(SensorComparisonSchema).max(6),
  candidate_outliers: z.array(CandidateOutlierSchema).max(500),
})
export type EdaSummaryResponse = z.infer<typeof EdaSummaryResponseSchema>

export const EdaDistributionQuerySchema = z
  .strictObject({
    deviceId: SensorIdSchema.optional(),
    from: Rfc3339Schema,
    to: Rfc3339Schema,
    field: EdaFieldSchema,
    bins: z.number().int().min(5).max(100).default(20),
  })
  .refine((value) => Date.parse(value.from) < Date.parse(value.to), {
    message: 'from must be earlier than to',
    path: ['from'],
  })
export type EdaDistributionQuery = z.input<typeof EdaDistributionQuerySchema>

export const DistributionSummarySchema = z.strictObject({
  min: z.number(),
  max: z.number(),
  mean: z.number(),
  median: z.number(),
  p05: z.number(),
  p95: z.number(),
})
export type DistributionSummary = z.infer<typeof DistributionSummarySchema>

export const HistogramBinSchema = z
  .strictObject({
    start: z.number(),
    end: z.number(),
    count: z.number().int().nonnegative(),
  })
  .refine((value) => value.start < value.end, {
    message: 'bin start must be less than bin end',
    path: ['start'],
  })
export type HistogramBin = z.infer<typeof HistogramBinSchema>

export const EdaDistributionResponseSchema = z.strictObject({
  request_id: z.string(),
  field: EdaFieldSchema,
  sample_count: z.number().int().nonnegative(),
  summary: DistributionSummarySchema,
  bins: z.array(HistogramBinSchema).max(100),
})
export const HistogramResponseSchema = EdaDistributionResponseSchema
export type EdaDistributionResponse = z.infer<typeof EdaDistributionResponseSchema>
export type HistogramResponse = EdaDistributionResponse

export const EdaCorrelationQuerySchema = z
  .strictObject({
    deviceId: SensorIdSchema.optional(),
    from: Rfc3339Schema,
    to: Rfc3339Schema,
    xField: EdaFieldSchema.default('temperature_c'),
    yField: EdaFieldSchema.default('relative_humidity_pct'),
    maxPoints: z.number().int().min(100).max(5_000).default(1_000),
    cursor: z.string().optional(),
  })
  .superRefine((value, context) => {
    if (Date.parse(value.from) >= Date.parse(value.to)) {
      context.addIssue({ code: 'custom', message: 'from must be earlier than to', path: ['from'] })
    }
    if (value.xField === value.yField) {
      context.addIssue({
        code: 'custom',
        message: 'xField and yField must differ',
        path: ['yField'],
      })
    }
  })
export type EdaCorrelationQuery = z.input<typeof EdaCorrelationQuerySchema>

export const CorrelationPointSchema = z.strictObject({
  ts: Rfc3339Schema,
  device_id: SensorIdSchema,
  x: z.number(),
  y: z.number(),
  score: z.number().optional(),
  is_candidate_outlier: z.boolean(),
})
export type CorrelationPoint = z.infer<typeof CorrelationPointSchema>

export const EdaCorrelationResponseSchema = z
  .strictObject({
    request_id: z.string(),
    x_field: EdaFieldSchema,
    y_field: EdaFieldSchema,
    sample_count: z.number().int().nonnegative(),
    correlation: z.number().min(-1).max(1).nullable(),
    points: z.array(CorrelationPointSchema).max(5_000),
    next_cursor: z.string().nullable(),
  })
  .refine((value) => value.x_field !== value.y_field, {
    message: 'x_field and y_field must differ',
    path: ['y_field'],
  })
export const CorrelationResponseSchema = EdaCorrelationResponseSchema
export type EdaCorrelationResponse = z.infer<typeof EdaCorrelationResponseSchema>
export type CorrelationResponse = EdaCorrelationResponse

import { z } from 'zod'
import {
  BucketSchema,
  CorpusDeviceIdSchema,
  HistoricalDateTimeSchema,
  SeveritySchema,
  compareHistoricalDateTimes,
} from './common'

export const ScoreProvenanceSchema = z.enum(['simulated_preview', 'artifact_backed'])

export const InferencePointSchema = z
  .strictObject({
    window_start_ts: HistoricalDateTimeSchema,
    window_end_ts: HistoricalDateTimeSchema,
    score_ts: HistoricalDateTimeSchema,
    score: z.number(),
    threshold: z.number(),
    is_anomaly: z.boolean(),
    severity: SeveritySchema.nullable(),
    latest_score: z.number().nullable(),
    sample_count: z.number().int().positive(),
    model_version: z.string(),
    score_provenance: ScoreProvenanceSchema,
    recon_temperature_c: z.number().nullable(),
    recon_relative_humidity_pct: z.number().nullable(),
    band_half_temperature_c: z.number().nonnegative().nullable(),
    band_half_relative_humidity_pct: z.number().nonnegative().nullable(),
  })
  .refine(
    (value) => compareHistoricalDateTimes(value.window_start_ts, value.window_end_ts) < 0,
    {
      message: 'window_start_ts must be earlier than window_end_ts',
      path: ['window_start_ts'],
    },
  )
  .refine(
    (value) => compareHistoricalDateTimes(value.window_end_ts, value.score_ts) <= 0,
    {
      message: 'score_ts must not be earlier than window_end_ts',
      path: ['score_ts'],
    },
  )
export type InferencePoint = z.infer<typeof InferencePointSchema>

export const InferenceQuerySchema = z
  .strictObject({
    deviceId: CorpusDeviceIdSchema,
    from: HistoricalDateTimeSchema,
    to: HistoricalDateTimeSchema,
    bucket: BucketSchema.default('raw'),
    limit: z.number().int().min(1).max(5_000).default(500),
    cursor: z.string().optional(),
    modelVersion: z.string().optional(),
  })
  .superRefine((value, context) => {
    if (compareHistoricalDateTimes(value.from, value.to) >= 0) {
      context.addIssue({ code: 'custom', message: 'from must be earlier than to', path: ['from'] })
    }
    if (value.bucket !== 'raw' && value.limit > 2_000) {
      context.addIssue({
        code: 'custom',
        message: 'bucketed limit must be at most 2000',
        path: ['limit'],
      })
    }
  })
export const InferenceResultsQuerySchema = InferenceQuerySchema
export type InferenceQuery = z.input<typeof InferenceQuerySchema>
export type InferenceResultsQuery = InferenceQuery

export const InferenceResponseSchema = z
  .strictObject({
    request_id: z.string(),
    device_id: CorpusDeviceIdSchema,
    from: HistoricalDateTimeSchema,
    to: HistoricalDateTimeSchema,
    bucket: BucketSchema,
    bucket_seconds: z.number().int().min(60).nullable(),
    time_zone: z.literal('Asia/Jakarta'),
    model_version: z.string(),
    points: z.array(InferencePointSchema).max(5_000),
    next_cursor: z.string().nullable(),
    returned_count: z.number().int().nonnegative(),
  })
  .superRefine((value, context) => {
    if (compareHistoricalDateTimes(value.from, value.to) >= 0) {
      context.addIssue({ code: 'custom', message: 'from must be earlier than to', path: ['from'] })
    }
    if (value.returned_count !== value.points.length) {
      context.addIssue({
        code: 'custom',
        message: 'returned_count must equal points length',
        path: ['returned_count'],
      })
    }
  })
  .refine(
    (value) => value.points.every((point) => point.model_version === value.model_version),
    {
      message: 'all points must belong to the selected model_version',
      path: ['points'],
    },
  )
export const InferenceResultsResponseSchema = InferenceResponseSchema
export type InferenceResponse = z.infer<typeof InferenceResponseSchema>
export type InferenceResultsResponse = InferenceResponse

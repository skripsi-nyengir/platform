import { z } from 'zod'
import {
  BucketSchema,
  CorpusDeviceIdSchema,
  HistoricalDateTimeSchema,
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
    model_version: z.string(),
    score_provenance: ScoreProvenanceSchema,
    recon_temperature_c: z.number().nullable().optional(),
    recon_relative_humidity_pct: z.number().nullable().optional(),
    band_half_temperature_c: z.number().nonnegative().nullable().optional(),
    band_half_relative_humidity_pct: z.number().nonnegative().nullable().optional(),
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
    time_zone: z.literal('Asia/Jakarta'),
    model_version: z.string(),
    points: z.array(InferencePointSchema).max(5_000),
    next_cursor: z.string().nullable(),
    returned_count: z.number().int().nonnegative(),
  })
  .refine((value) => value.returned_count === value.points.length, {
    message: 'returned_count must equal points length',
    path: ['returned_count'],
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

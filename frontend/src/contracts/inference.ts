import { z } from 'zod'
import { BucketSchema, Rfc3339Schema, SensorIdSchema } from './common'

export const InferencePointSchema = z
  .strictObject({
    window_start_ts: Rfc3339Schema,
    window_end_ts: Rfc3339Schema,
    score: z.number(),
    threshold: z.number(),
    is_anomaly: z.boolean(),
    model_version: z.string(),
    model_hash: z.string(),
    preprocessing_hash: z.string(),
    threshold_hash: z.string(),
  })
  .refine((value) => Date.parse(value.window_start_ts) < Date.parse(value.window_end_ts), {
    message: 'window_start_ts must be earlier than window_end_ts',
    path: ['window_start_ts'],
  })
export type InferencePoint = z.infer<typeof InferencePointSchema>

export const InferenceQuerySchema = z
  .strictObject({
    deviceId: SensorIdSchema,
    from: Rfc3339Schema,
    to: Rfc3339Schema,
    bucket: BucketSchema.default('raw'),
    limit: z.number().int().min(1).max(5_000).default(500),
    cursor: z.string().optional(),
    modelVersion: z.string().optional(),
  })
  .superRefine((value, context) => {
    if (Date.parse(value.from) >= Date.parse(value.to)) {
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
    device_id: SensorIdSchema,
    model_version: z.string(),
    points: z.array(InferencePointSchema).max(5_000),
    next_cursor: z.string().nullable(),
    returned_count: z.number().int().nonnegative(),
  })
  .refine((value) => value.returned_count === value.points.length, {
    message: 'returned_count must equal points length',
    path: ['returned_count'],
  })
export const InferenceResultsResponseSchema = InferenceResponseSchema
export type InferenceResponse = z.infer<typeof InferenceResponseSchema>
export type InferenceResultsResponse = InferenceResponse

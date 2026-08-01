import { z } from 'zod'
import {
  CorpusDeviceIdSchema,
  HistoricalDateTimeSchema,
  compareHistoricalDateTimes,
} from './common'

export const PostInferenceBinSchema = z
  .strictObject({
    segment_id: z.number().int(),
    bin_ordinal: z.number().int().nonnegative(),
    start_score_ts: HistoricalDateTimeSchema,
    end_score_ts: HistoricalDateTimeSchema,
    scored_timestamp_count: z.number().int(),
    is_alert: z.boolean(),
    candidate_alert_count: z.number().int().nonnegative(),
    first_alert_ts: HistoricalDateTimeSchema.nullable(),
    last_alert_ts: HistoricalDateTimeSchema.nullable(),
    peak_score: z.number(),
    latest_score: z.number(),
    threshold: z.number(),
    schema_version: z.string(),
  })
  .refine(
    (value) =>
      compareHistoricalDateTimes(value.start_score_ts, value.end_score_ts) <= 0,
    {
      message: 'start_score_ts must not be later than end_score_ts',
      path: ['start_score_ts'],
    },
  )
export type PostInferenceBin = z.infer<typeof PostInferenceBinSchema>

export const PostInferenceBinSourceSchema = z.enum(['replay', 'live'])
export type PostInferenceBinSource = z.infer<typeof PostInferenceBinSourceSchema>

export const PostInferenceBinsQuerySchema = z
  .strictObject({
    deviceId: CorpusDeviceIdSchema,
    from: HistoricalDateTimeSchema,
    to: HistoricalDateTimeSchema,
    source: PostInferenceBinSourceSchema.default('replay'),
    limit: z.number().int().min(1).max(5_000).default(500),
    cursor: z.string().optional(),
    modelVersion: z.string().optional(),
  })
  .superRefine((value, context) => {
    if (compareHistoricalDateTimes(value.from, value.to) >= 0) {
      context.addIssue({ code: 'custom', message: 'from must be earlier than to', path: ['from'] })
    }
  })
export type PostInferenceBinsQuery = z.input<typeof PostInferenceBinsQuerySchema>

export const PostInferenceBinsResponseSchema = z
  .strictObject({
    request_id: z.string(),
    device_id: CorpusDeviceIdSchema,
    from: HistoricalDateTimeSchema,
    to: HistoricalDateTimeSchema,
    time_zone: z.literal('Asia/Jakarta'),
    source: PostInferenceBinSourceSchema,
    model_version: z.string(),
    bins: z.array(PostInferenceBinSchema).max(5_000),
    next_cursor: z.string().nullable(),
    returned_count: z.number().int().nonnegative(),
  })
  .superRefine((value, context) => {
    if (compareHistoricalDateTimes(value.from, value.to) >= 0) {
      context.addIssue({ code: 'custom', message: 'from must be earlier than to', path: ['from'] })
    }
    if (value.returned_count !== value.bins.length) {
      context.addIssue({
        code: 'custom',
        message: 'returned_count must equal bins length',
        path: ['returned_count'],
      })
    }
  })
export type PostInferenceBinsResponse = z.infer<typeof PostInferenceBinsResponseSchema>

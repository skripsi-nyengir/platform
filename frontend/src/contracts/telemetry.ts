import { z } from 'zod'
import {
  AvailabilitySchema,
  BucketSchema,
  FreshnessSchema,
  HistoricalDateTimeSchema,
  OperationalInstantSchema,
  SensorIdSchema,
  compareHistoricalDateTimes,
} from './common'

export const LatestTelemetrySensorSchema = z.strictObject({
  device_id: SensorIdSchema,
  ts: HistoricalDateTimeSchema.nullable(),
  temperature_c: z.number().nullable(),
  relative_humidity_pct: z.number().nullable(),
  freshness: FreshnessSchema,
  age_seconds: z.number().nonnegative().nullable(),
  availability: AvailabilitySchema,
})
export type LatestTelemetrySensor = z.infer<typeof LatestTelemetrySensorSchema>

export const LatestTelemetryResponseSchema = z.strictObject({
  request_id: z.string(),
  time_zone: z.literal('Asia/Jakarta'),
  generated_at: OperationalInstantSchema,
  sensors: z.array(LatestTelemetrySensorSchema).max(2),
})
export type LatestTelemetryResponse = z.infer<typeof LatestTelemetryResponseSchema>

export const TelemetryPointSchema = z.strictObject({
  ts: HistoricalDateTimeSchema,
  temperature_c: z.number().nullable(),
  relative_humidity_pct: z.number().nullable(),
  sample_count: z.number().int().nonnegative(),
  gap_before: z.boolean(),
})
export type TelemetryPoint = z.infer<typeof TelemetryPointSchema>

export const TelemetryHistoryQuerySchema = z
  .strictObject({
    deviceId: SensorIdSchema,
    from: HistoricalDateTimeSchema,
    to: HistoricalDateTimeSchema,
    bucket: BucketSchema.default('raw'),
    limit: z.number().int().min(1).max(5_000).default(500),
    cursor: z.string().optional(),
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
export type TelemetryHistoryQuery = z.input<typeof TelemetryHistoryQuerySchema>

export const TelemetryHistoryResponseSchema = z
  .strictObject({
    request_id: z.string(),
    device_id: SensorIdSchema,
    time_zone: z.literal('Asia/Jakarta'),
    from: HistoricalDateTimeSchema,
    to: HistoricalDateTimeSchema,
    bucket: BucketSchema,
    points: z.array(TelemetryPointSchema).max(5_000),
    next_cursor: z.string().nullable(),
    returned_count: z.number().int().nonnegative(),
  })
  .superRefine((value, context) => {
    if (compareHistoricalDateTimes(value.from, value.to) >= 0) {
      context.addIssue({ code: 'custom', message: 'from must be earlier than to', path: ['from'] })
    }
    if (value.bucket !== 'raw' && value.points.length > 2_000) {
      context.addIssue({
        code: 'custom',
        message: 'bucketed responses contain at most 2000 points',
        path: ['points'],
      })
    }
    if (value.returned_count !== value.points.length) {
      context.addIssue({
        code: 'custom',
        message: 'returned_count must equal points length',
        path: ['returned_count'],
      })
    }
  })
export type TelemetryHistoryResponse = z.infer<typeof TelemetryHistoryResponseSchema>

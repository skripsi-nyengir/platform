import { z } from 'zod'

export const sensorIds = ['n1', 'n2', 'n3', 'n4', 'n5', 'n6'] as const
export const SensorIdSchema = z.enum(sensorIds)
export type SensorId = z.infer<typeof SensorIdSchema>

export const BucketSchema = z.enum(['raw', '1m', '5m', '15m', '1h', '1d'])
export type Bucket = z.infer<typeof BucketSchema>

export const FreshnessSchema = z.enum(['fresh', 'stale', 'unknown'])
export type Freshness = z.infer<typeof FreshnessSchema>

export const AvailabilitySchema = z.enum(['online', 'offline', 'unknown'])
export type Availability = z.infer<typeof AvailabilitySchema>

export const AlertStatusSchema = z.enum(['detected', 'acknowledged', 'resolved'])
export type AlertStatus = z.infer<typeof AlertStatusSchema>

export const Rfc3339Schema = z.iso.datetime({ offset: true })

export const ProblemDetailsSchema = z.strictObject({
  type: z.url(),
  title: z.string(),
  status: z.number().int(),
  detail: z.string(),
  instance: z.string(),
  request_id: z.string(),
  errors: z.record(z.string(), z.array(z.string())).optional(),
})
export type ProblemDetails = z.infer<typeof ProblemDetailsSchema>

export const AlertCommandRequestSchema = z.strictObject({
  command_id: z.string(),
  event_ts: Rfc3339Schema,
  note: z.string().optional(),
})
export type AlertCommandRequest = z.infer<typeof AlertCommandRequestSchema>

export type ApiPath = `/api/${string}` | '/health' | '/ready'

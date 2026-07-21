import { z } from 'zod'
import { Rfc3339Schema } from './common'

export const LivenessStateSchema = z.enum(['alive', 'not_alive', 'unknown'])
export type LivenessState = z.infer<typeof LivenessStateSchema>

export const ReadinessStateSchema = z.enum(['ready', 'not_ready', 'unknown'])
export type ReadinessState = z.infer<typeof ReadinessStateSchema>

export const SystemServiceStatusSchema = z.strictObject({
  name: z.string(),
  liveness: LivenessStateSchema,
  readiness: ReadinessStateSchema,
  checked_at: Rfc3339Schema,
  detail: z.string(),
})
export type SystemServiceStatus = z.infer<typeof SystemServiceStatusSchema>

export const SystemTelemetryStatusSchema = z
  .strictObject({
    latest_ts: Rfc3339Schema.nullable(),
    age_seconds: z.number().nonnegative().nullable(),
    fresh_sensor_count: z.number().int().min(0).max(6),
    stale_sensor_count: z.number().int().min(0).max(6),
    offline_sensor_count: z.number().int().min(0).max(6),
  })
  .refine(
    (value) =>
      value.fresh_sensor_count + value.stale_sensor_count + value.offline_sensor_count <= 6,
    {
      message: 'telemetry sensor counts must not exceed six sensors',
      path: ['fresh_sensor_count'],
    },
  )
export type SystemTelemetryStatus = z.infer<typeof SystemTelemetryStatusSchema>

export const DiagnosticsSchema = z
  .record(z.string(), z.json())
  .refine((value) => Object.keys(value).length <= 500, {
    message: 'diagnostics must contain at most 500 entries',
  })

export const SystemStatusResponseSchema = z.strictObject({
  request_id: z.string(),
  checked_at: Rfc3339Schema,
  overall_observation: z.string(),
  services: z.array(SystemServiceStatusSchema).max(500),
  telemetry: SystemTelemetryStatusSchema,
  diagnostics: DiagnosticsSchema.optional(),
})
export type SystemStatusResponse = z.infer<typeof SystemStatusResponseSchema>

export const LivenessResponseSchema = z.strictObject({
  status: z.literal('alive'),
  request_id: z.string(),
  checked_at: Rfc3339Schema,
})
export type LivenessResponse = z.infer<typeof LivenessResponseSchema>

export const ReadinessDependencySchema = z.strictObject({
  name: z.string(),
  status: ReadinessStateSchema,
  detail: z.string(),
})
export type ReadinessDependency = z.infer<typeof ReadinessDependencySchema>

export const ReadinessResponseSchema = z.strictObject({
  status: z.enum(['ready', 'not_ready']),
  request_id: z.string(),
  checked_at: Rfc3339Schema,
  dependencies: z.array(ReadinessDependencySchema).max(500),
})
export type ReadinessResponse = z.infer<typeof ReadinessResponseSchema>

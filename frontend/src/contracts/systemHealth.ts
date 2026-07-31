import { z } from 'zod'
import { HistoricalDateTimeSchema, OperationalInstantSchema } from './common'

export const LivenessStateSchema = z.enum(['alive', 'not_alive', 'unknown'])
export type LivenessState = z.infer<typeof LivenessStateSchema>

export const ReadinessStateSchema = z.enum(['ready', 'not_ready', 'unknown'])
export type ReadinessState = z.infer<typeof ReadinessStateSchema>

export const SystemServiceStatusSchema = z.strictObject({
  name: z.string(),
  liveness: LivenessStateSchema,
  readiness: ReadinessStateSchema,
  checked_at: OperationalInstantSchema,
  detail: z.string(),
})
export type SystemServiceStatus = z.infer<typeof SystemServiceStatusSchema>

export const SystemTelemetryStatusSchema = z
  .strictObject({
    classification: z.enum(['healthy', 'degraded', 'failed']),
    reasons: z.array(z.string()).max(20),
    configuration_valid: z.boolean(),
    lease_active: z.boolean(),
    fencing_token: z.number().int().positive().nullable(),
    database_heartbeat: OperationalInstantSchema.nullable(),
    connection_state: z.enum(['connected', 'subscribed', 'disconnected', 'unknown']),
    connack_received: z.boolean().nullable(),
    suback_received: z.boolean().nullable(),
    latest_ts: HistoricalDateTimeSchema.nullable(),
    last_valid_reading_ts: HistoricalDateTimeSchema.nullable(),
    last_valid_reading_at: OperationalInstantSchema.nullable(),
    age_seconds: z.number().nonnegative().nullable(),
    last_gap_at: OperationalInstantSchema.nullable(),
    invalid_message_count: z.number().int().nonnegative().nullable(),
    retained_message_count: z.number().int().nonnegative().nullable(),
    last_persistence_failure_at: OperationalInstantSchema.nullable(),
    ingress_queue_depth: z.number().int().nonnegative().nullable(),
    dropped_newest_count: z.number().int().nonnegative().nullable(),
    pending_boundary_count: z.number().int().nonnegative(),
    durable_backlog_count: z.number().int().nonnegative(),
    cursor_ts: HistoricalDateTimeSchema.nullable(),
    cursor_id: z.string().nullable(),
    recovery_ready: z.boolean(),
    active_model_version: z.string().nullable(),
    active_scaler_corpus_id: z.string().nullable(),
    artifact_hashes: z.record(z.string(), z.string()),
    retry_state: z.enum(['idle', 'retrying', 'unknown']),
    fresh_sensor_count: z.number().int().min(0).max(1),
    stale_sensor_count: z.number().int().min(0).max(1),
    offline_sensor_count: z.number().int().min(0).max(1),
  })
  .refine(
    (value) =>
      value.fresh_sensor_count + value.stale_sensor_count + value.offline_sensor_count <= 1,
    {
      message: 'telemetry sensor counts must not exceed one public device',
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
  checked_at: OperationalInstantSchema,
  overall_observation: z.string(),
  services: z.array(SystemServiceStatusSchema).max(500),
  telemetry: SystemTelemetryStatusSchema,
  diagnostics: DiagnosticsSchema.optional(),
})
export type SystemStatusResponse = z.infer<typeof SystemStatusResponseSchema>

export const LivenessResponseSchema = z.strictObject({
  status: z.literal('alive'),
  request_id: z.string(),
  checked_at: OperationalInstantSchema,
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
  checked_at: OperationalInstantSchema,
  dependencies: z.array(ReadinessDependencySchema).max(500),
})
export type ReadinessResponse = z.infer<typeof ReadinessResponseSchema>

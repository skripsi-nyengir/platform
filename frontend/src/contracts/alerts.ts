import { z } from 'zod'
import {
  AlertStatusSchema,
  HistoricalDateTimeSchema,
  OperationalInstantSchema,
  SensorIdSchema,
} from './common'
import { InferencePointSchema } from './inference'
import { TelemetryPointSchema } from './telemetry'

export const DetectionBasisSchema = z.enum(['simulated_preview', 'artifact_backed'])

export const AlertEventSchema = z.strictObject({
  event_id: z.string(),
  alert_id: z.string(),
  event_at: OperationalInstantSchema,
  event_type: AlertStatusSchema,
  device_id: SensorIdSchema,
  actor: z.string(),
  note: z.string().nullable(),
  accepted_at: OperationalInstantSchema.nullable(),
  inference_model_version: z.string().nullable(),
  detection_basis: DetectionBasisSchema,
})
export type AlertEvent = z.infer<typeof AlertEventSchema>

export const AlertEventsQuerySchema = z
  .strictObject({
    alertId: z.string().min(1).optional(),
    deviceId: SensorIdSchema.optional(),
    from: OperationalInstantSchema.optional(),
    to: OperationalInstantSchema.optional(),
    limit: z.number().int().min(1).max(200).default(200),
    cursor: z.string().optional(),
  })
  .superRefine((value, context) => {
    if (
      value.from !== undefined &&
      value.to !== undefined &&
      Date.parse(value.from) >= Date.parse(value.to)
    ) {
      context.addIssue({ code: 'custom', message: 'from must be earlier than to', path: ['from'] })
    }
  })
export type AlertEventsQuery = z.input<typeof AlertEventsQuerySchema>

export const AlertEventsResponseSchema = z
  .strictObject({
    request_id: z.string(),
    time_zone: z.literal('Asia/Jakarta'),
    from: OperationalInstantSchema.nullable(),
    to: OperationalInstantSchema,
    events: z.array(AlertEventSchema).max(200),
    next_cursor: z.string().nullable(),
    returned_count: z.number().int().nonnegative(),
  })
  .refine((value) => value.returned_count === value.events.length, {
    message: 'returned_count must equal events length',
    path: ['returned_count'],
  })
export type AlertEventsResponse = z.infer<typeof AlertEventsResponseSchema>

export const CurrentAlertSchema = z
  .strictObject({
    alert_id: z.string(),
    device_id: SensorIdSchema,
    status: AlertStatusSchema,
    episode_start_ts: HistoricalDateTimeSchema,
    episode_end_ts: HistoricalDateTimeSchema,
    last_score_ts: HistoricalDateTimeSchema,
    created_at: OperationalInstantSchema,
    latest_event_at: OperationalInstantSchema,
    latest_event_id: z.string(),
    peak_score: z.number(),
    latest_score: z.number(),
    anomalous_window_count: z.number().int().positive(),
    replay_job_id: z.string().nullable(),
    threshold: z.number(),
    model_version: z.string(),
    detection_basis: DetectionBasisSchema,
    can_acknowledge: z.boolean(),
    can_resolve: z.boolean(),
  })
  .superRefine((value, context) => {
    const permissions = {
      detected: { can_acknowledge: true, can_resolve: false },
      acknowledged: { can_acknowledge: false, can_resolve: true },
      resolved: { can_acknowledge: false, can_resolve: false },
    }[value.status]
    if (value.can_acknowledge !== permissions.can_acknowledge) {
      context.addIssue({
        code: 'custom',
        message: `can_acknowledge is invalid for ${value.status}`,
        path: ['can_acknowledge'],
      })
    }
    if (value.can_resolve !== permissions.can_resolve) {
      context.addIssue({
        code: 'custom',
        message: `can_resolve is invalid for ${value.status}`,
        path: ['can_resolve'],
      })
    }
  })
export type CurrentAlert = z.infer<typeof CurrentAlertSchema>

export const CurrentAlertsQuerySchema = z.strictObject({
  deviceId: SensorIdSchema.optional(),
  status: AlertStatusSchema.optional(),
  page: z.number().int().min(1).default(1),
  pageSize: z.number().int().min(1).max(100).default(25),
})
export type CurrentAlertsQuery = z.input<typeof CurrentAlertsQuerySchema>

export const CurrentAlertsResponseSchema = z
  .strictObject({
    request_id: z.string(),
    time_zone: z.literal('Asia/Jakarta'),
    generated_at: OperationalInstantSchema,
    items: z.array(CurrentAlertSchema).max(100),
    page: z.number().int().min(1),
    page_size: z.number().int().min(1).max(100),
    total: z.number().int().nonnegative(),
  })
  .superRefine((value, context) => {
    if (value.total < value.items.length) {
      context.addIssue({
        code: 'custom',
        message: 'total must be at least the number of returned items',
        path: ['total'],
      })
    }
    if (value.items.length > value.page_size) {
      context.addIssue({
        code: 'custom',
        message: 'items length must not exceed page_size',
        path: ['items'],
      })
    }
  })
export type CurrentAlertsResponse = z.infer<typeof CurrentAlertsResponseSchema>

export const AlertContextPointSchema = z.strictObject({
  inference: InferencePointSchema,
  source_readings: z.array(TelemetryPointSchema).length(10),
})
export type AlertContextPoint = z.infer<typeof AlertContextPointSchema>

export const AlertDetailResponseSchema = z.strictObject({
  request_id: z.string(),
  time_zone: z.literal('Asia/Jakarta'),
  alert: CurrentAlertSchema,
  context_before: z.array(TelemetryPointSchema).max(10),
  episode_points: z.array(AlertContextPointSchema),
  recovery_points: z.array(AlertContextPointSchema).max(3),
})
export type AlertDetailResponse = z.infer<typeof AlertDetailResponseSchema>

export const AcknowledgeAlertResponseSchema = z
  .strictObject({
    request_id: z.string(),
    alert_id: z.string(),
    status: z.literal('acknowledged'),
    event: AlertEventSchema,
    idempotent_replay: z.boolean(),
  })
  .superRefine((value, context) => {
    if (value.event.alert_id !== value.alert_id) {
      context.addIssue({
        code: 'custom',
        message: 'event alert_id must match response alert_id',
        path: ['event', 'alert_id'],
      })
    }
    if (value.event.event_type !== 'acknowledged') {
      context.addIssue({
        code: 'custom',
        message: 'acknowledgement event must be acknowledged',
        path: ['event', 'event_type'],
      })
    }
  })
export type AcknowledgeAlertResponse = z.infer<typeof AcknowledgeAlertResponseSchema>

export const ResolveAlertResponseSchema = z
  .strictObject({
    request_id: z.string(),
    alert_id: z.string(),
    status: z.literal('resolved'),
    event: AlertEventSchema,
    idempotent_replay: z.boolean(),
  })
  .superRefine((value, context) => {
    if (value.event.alert_id !== value.alert_id) {
      context.addIssue({
        code: 'custom',
        message: 'event alert_id must match response alert_id',
        path: ['event', 'alert_id'],
      })
    }
    if (value.event.event_type !== 'resolved') {
      context.addIssue({
        code: 'custom',
        message: 'resolution event must be resolved',
        path: ['event', 'event_type'],
      })
    }
  })
export type ResolveAlertResponse = z.infer<typeof ResolveAlertResponseSchema>

export const AlertMutationResponseSchema = z.union([
  AcknowledgeAlertResponseSchema,
  ResolveAlertResponseSchema,
])
export type AlertMutationResponse = z.infer<typeof AlertMutationResponseSchema>

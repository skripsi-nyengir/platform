import { z } from 'zod'
import {
  CorpusDeviceIdSchema,
  HistoricalDateTimeSchema,
  OperationalInstantSchema,
  SensorIdSchema,
  compareHistoricalDateTimes,
} from './common'
import { ScoreProvenanceSchema } from './inference'

export const ImportReadinessSchema = z.enum(['pending', 'importing', 'ready', 'failed'])
export const DeviceSchema = z.strictObject({
  device_id: SensorIdSchema,
  display_name: z.literal('TALPHA Ruang Produksi'),
  time_zone: z.literal('Asia/Jakarta'),
  channels: z.tuple([z.literal('suhu'), z.literal('rh')]),
  corpus_from: HistoricalDateTimeSchema.nullable(),
  corpus_to: HistoricalDateTimeSchema.nullable(),
  import_readiness: ImportReadinessSchema,
})
export type Device = z.infer<typeof DeviceSchema>

export const DevicesResponseSchema = z.strictObject({
  request_id: z.string(),
  items: z.array(DeviceSchema).length(1),
})
export type DevicesResponse = z.infer<typeof DevicesResponseSchema>

export const ReplayStatusSchema = z.enum(['queued', 'running', 'succeeded', 'failed'])
export const ReplayJobRequestSchema = z
  .strictObject({
    command_id: z.string().uuid(),
    device_id: CorpusDeviceIdSchema,
    from: HistoricalDateTimeSchema,
    to: HistoricalDateTimeSchema,
  })
  .superRefine((value, context) => {
    if (compareHistoricalDateTimes(value.from, value.to) >= 0) {
      context.addIssue({ code: 'custom', message: 'from must be earlier than to', path: ['from'] })
      return
    }
    const from = new Date(`${value.from}+07:00`)
    const to = new Date(`${value.to}+07:00`)
    if (to.getTime() - from.getTime() > 31 * 24 * 60 * 60 * 1_000) {
      context.addIssue({ code: 'custom', message: 'replay interval must not exceed 31 days', path: ['to'] })
    }
  })
export type ReplayJobRequest = z.infer<typeof ReplayJobRequestSchema>

export const ReplayJobSchema = z.strictObject({
  job_id: z.string(),
  device_id: CorpusDeviceIdSchema,
  from: HistoricalDateTimeSchema,
  to: HistoricalDateTimeSchema,
  time_zone: z.literal('Asia/Jakarta'),
  model_version: z.string(),
  activation_id: z.string(),
  score_provenance: ScoreProvenanceSchema,
  status: ReplayStatusSchema,
  progress: z.number().min(0).max(1),
  processed_count: z.number().int().nonnegative(),
  result_count: z.number().int().nonnegative(),
  episode_count: z.number().int().nonnegative(),
  submitted_at: OperationalInstantSchema,
  started_at: OperationalInstantSchema.nullable(),
  completed_at: OperationalInstantSchema.nullable(),
  error_code: z.string().nullable(),
  error_detail: z.string().nullable(),
})
export type ReplayJob = z.infer<typeof ReplayJobSchema>

export const ReplayJobResponseSchema = z.strictObject({
  request_id: z.string(),
  job: ReplayJobSchema,
  idempotent_request_replay: z.boolean(),
})
export type ReplayJobResponse = z.infer<typeof ReplayJobResponseSchema>

export const ReplayJobStatusResponseSchema = z.strictObject({
  request_id: z.string(),
  job: ReplayJobSchema,
})
export type ReplayJobStatusResponse = z.infer<typeof ReplayJobStatusResponseSchema>

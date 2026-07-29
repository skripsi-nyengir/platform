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

export const ArtifactStatusSchema = z.enum(['pending', 'ready'])
export const RuntimeKindSchema = z.enum(['preview_simulator', 'artifact'])
export const ModelVersionSchema = z.strictObject({
  version: z.string().min(1),
  runtime_kind: RuntimeKindSchema,
  selectable: z.boolean(),
  compatible: z.boolean(),
  artifact_status: ArtifactStatusSchema,
  score_provenance: ScoreProvenanceSchema,
})
export type ModelVersion = z.infer<typeof ModelVersionSchema>

export const ModelFamilySchema = z.strictObject({
  model_key: z.enum([
    'ewma',
    'pca',
    'wsn-dense-ae',
    'lstm-ae',
    'usad',
    'cfc-autoencoder',
    'mtad-gat',
  ]),
  display_name: z.string().min(1),
  artifact_status: ArtifactStatusSchema,
  versions: z.array(ModelVersionSchema).min(1),
})
export type ModelFamily = z.infer<typeof ModelFamilySchema>

export const ModelsResponseSchema = z.strictObject({
  request_id: z.string(),
  device_id: SensorIdSchema,
  active_activation_id: z.string(),
  active_model_version: z.string(),
  families: z.array(ModelFamilySchema).length(7),
})
export type ModelsResponse = z.infer<typeof ModelsResponseSchema>

export const ModelActivationRequestSchema = z.strictObject({
  command_id: z.string().uuid(),
  device_id: SensorIdSchema,
  model_version: z.string().min(1),
})
export type ModelActivationRequest = z.infer<typeof ModelActivationRequestSchema>

export const ModelActivationSchema = z.strictObject({
  activation_id: z.string(),
  command_id: z.string(),
  device_id: SensorIdSchema,
  prior_model_version: z.string().nullable(),
  model_version: z.string(),
  changed: z.boolean(),
  activated_at: OperationalInstantSchema,
  actor: z.string(),
})
export const ModelActivationResponseSchema = z.strictObject({
  request_id: z.string(),
  activation: ModelActivationSchema,
  active_model_version: z.string(),
  idempotent_request_replay: z.boolean(),
})
export type ModelActivationResponse = z.infer<typeof ModelActivationResponseSchema>

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

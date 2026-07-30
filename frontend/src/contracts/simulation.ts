import { z } from 'zod'
import { simDeviceId } from './common'

export const SimModelVersionSchema = z.enum([
  'artifact-lstm-ae-v3',
  'artifact-conv1d-v3',
  'artifact-transformer-v3',
  'artifact-gru-v3',
  'artifact-rnn-v3',
])
export type SimModelVersion = z.infer<typeof SimModelVersionSchema>

export const simModelWindowSizes = Object.freeze({
  'artifact-lstm-ae-v3': 30,
  'artifact-conv1d-v3': 30,
  'artifact-transformer-v3': 30,
  'artifact-gru-v3': 10,
  'artifact-rnn-v3': 10,
} satisfies Readonly<Record<SimModelVersion, number>>)

export const SimModelSchema = z.strictObject({
  version: SimModelVersionSchema,
  model_key: z.string().min(1),
  display_name: z.string().min(1),
  score_key: z.string().min(1),
  threshold: z.number(),
  manifest_sha256: z.string().min(1),
  is_active: z.boolean(),
})
export type SimModel = z.infer<typeof SimModelSchema>

export const SimModelsResponseSchema = z.strictObject({
  request_id: z.string(),
  device_id: z.literal(simDeviceId),
  models: z.array(SimModelSchema),
})
export type SimModelsResponse = z.infer<typeof SimModelsResponseSchema>

export const SetSimActiveModelRequestSchema = z.strictObject({
  model_version: z.string().min(1),
})
export type SetSimActiveModelRequest = z.infer<typeof SetSimActiveModelRequestSchema>

export const SetSimActiveModelResponseSchema = z.strictObject({
  request_id: z.string(),
  device_id: z.literal(simDeviceId),
  active_model_version: z.string().min(1),
})
export type SetSimActiveModelResponse = z.infer<typeof SetSimActiveModelResponseSchema>

export const SimulationScopeMetricsSchema = z
  .strictObject({
    scope: z.enum([
      'timestamp',
      'overlapping_model_windows',
      'non_overlapping_evaluation_bins',
    ]),
    precision: z.number().min(0).max(1),
    recall: z.number().min(0).max(1),
    f1: z.number().min(0).max(1),
    accuracy: z.number().min(0).max(1),
    tn: z.number().int().nonnegative(),
    fp: z.number().int().nonnegative(),
    fn: z.number().int().nonnegative(),
    tp: z.number().int().nonnegative(),
    n_evaluated: z.number().int().nonnegative(),
    n_anomalous: z.number().int().nonnegative(),
  })
  .refine((value) => value.tn + value.fp + value.fn + value.tp === value.n_evaluated, {
    message: 'confusion counts must equal n_evaluated',
    path: ['n_evaluated'],
  })
export type SimulationScopeMetrics = z.infer<typeof SimulationScopeMetricsSchema>

export const SimulationOperationalEventSchema = z
  .strictObject({
    segment_id: z.number().int().nonnegative(),
    start_idx: z.number().int().nonnegative(),
    end_idx: z.number().int().nonnegative(),
    n_candidates: z.number().int().positive(),
    peak_score: z.number(),
  })
  .refine((value) => value.start_idx <= value.end_idx, {
    message: 'start_idx must not be later than end_idx',
    path: ['start_idx'],
  })
export type SimulationOperationalEvent = z.infer<typeof SimulationOperationalEventSchema>

export const SimulationMetricsQuerySchema = z.strictObject({
  modelVersion: SimModelVersionSchema,
  cooldownSamples: z.number().int().min(1).default(10),
})
export type SimulationMetricsQuery = z.input<typeof SimulationMetricsQuerySchema>

const TimestampScopeSchema = SimulationScopeMetricsSchema.safeExtend({
  scope: z.literal('timestamp'),
})
const OverlappingScopeSchema = SimulationScopeMetricsSchema.safeExtend({
  scope: z.literal('overlapping_model_windows'),
})
const BinsScopeSchema = SimulationScopeMetricsSchema.safeExtend({
  scope: z.literal('non_overlapping_evaluation_bins'),
})

export const SimulationMetricsResponseSchema = z
  .strictObject({
    request_id: z.string(),
    device_id: z.literal(simDeviceId),
    model_version: SimModelVersionSchema,
    threshold: z.number(),
    window_size: z.number().int().positive(),
    frame_count: z.number().int().nonnegative(),
    event_count: z.number().int().nonnegative(),
    scored_windows: z.number().int().nonnegative(),
    timestamp_scope: TimestampScopeSchema,
    overlapping_scope: OverlappingScopeSchema,
    bins_scope: BinsScopeSchema,
    operational_event_count: z.number().int().nonnegative(),
    operational_events: z.array(SimulationOperationalEventSchema),
  })
  .refine(
    (value) => value.operational_event_count === value.operational_events.length,
    {
      message: 'operational_event_count must equal operational_events length',
      path: ['operational_event_count'],
    },
  )
export type SimulationMetricsResponse = z.infer<typeof SimulationMetricsResponseSchema>

import { z } from 'zod'
import { simDeviceId } from './common'

export const SimModelSchema = z.strictObject({
  version: z.string().min(1),
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

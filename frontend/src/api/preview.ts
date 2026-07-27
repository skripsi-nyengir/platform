import {
  DevicesResponseSchema,
  ModelActivationRequestSchema,
  ModelActivationResponseSchema,
  ModelsResponseSchema,
  ReplayJobRequestSchema,
  ReplayJobResponseSchema,
  ReplayJobStatusResponseSchema,
  type DevicesResponse,
  type ModelActivationRequest,
  type ModelActivationResponse,
  type ModelsResponse,
  type ReplayJobRequest,
  type ReplayJobResponse,
  type ReplayJobStatusResponse,
} from '../contracts/preview'
import { SensorIdSchema, type SensorId } from '../contracts/common'
import { requestJson } from './http'

export function getDevices(signal?: AbortSignal): Promise<DevicesResponse> {
  return requestJson('/api/devices', DevicesResponseSchema, { signal })
}

export function getModels(
  deviceId: SensorId,
  signal?: AbortSignal,
): Promise<ModelsResponse> {
  const id = SensorIdSchema.parse(deviceId)
  return requestJson(`/api/models?device_id=${encodeURIComponent(id)}`, ModelsResponseSchema, { signal })
}

export function activateModel(
  input: ModelActivationRequest,
  signal?: AbortSignal,
): Promise<ModelActivationResponse> {
  const body = ModelActivationRequestSchema.parse(input)
  return requestJson('/api/model-activations', ModelActivationResponseSchema, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
}

export function createReplayJob(
  input: ReplayJobRequest,
  signal?: AbortSignal,
): Promise<ReplayJobResponse> {
  const body = ReplayJobRequestSchema.parse(input)
  return requestJson('/api/replay-jobs', ReplayJobResponseSchema, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
}

export function getReplayJob(
  jobId: string,
  signal?: AbortSignal,
): Promise<ReplayJobStatusResponse> {
  if (jobId.length === 0) throw new Error('jobId is required')
  return requestJson(
    `/api/replay-jobs/${encodeURIComponent(jobId)}`,
    ReplayJobStatusResponseSchema,
    { signal },
  )
}

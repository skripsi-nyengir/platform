import {
  SetSimActiveModelRequestSchema,
  SetSimActiveModelResponseSchema,
  SimulationMetricsQuerySchema,
  SimulationMetricsResponseSchema,
  SimModelsResponseSchema,
  type SetSimActiveModelResponse,
  type SimulationMetricsQuery,
  type SimulationMetricsResponse,
  type SimModelsResponse,
} from '../contracts/simulation'
import { requestJson } from './http'

export function getSimulationModels(signal?: AbortSignal): Promise<SimModelsResponse> {
  return requestJson('/api/simulation/models', SimModelsResponseSchema, { signal })
}

export function getSimulationMetrics(
  input: SimulationMetricsQuery,
  signal?: AbortSignal,
): Promise<SimulationMetricsResponse> {
  const queryInput = SimulationMetricsQuerySchema.parse(input)
  const query = new URLSearchParams({
    model_version: queryInput.modelVersion,
    cooldown_samples: String(queryInput.cooldownSamples),
  })
  if (queryInput.bucketHours !== undefined) {
    query.set('bucket_hours', String(queryInput.bucketHours))
  }
  return requestJson(`/api/simulation/metrics?${query}`, SimulationMetricsResponseSchema, {
    signal,
  })
}

export function setSimulationActiveModel(
  model_version: string,
  signal?: AbortSignal,
): Promise<SetSimActiveModelResponse> {
  const body = SetSimActiveModelRequestSchema.parse({ model_version })
  return requestJson('/api/simulation/active-model', SetSimActiveModelResponseSchema, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
}

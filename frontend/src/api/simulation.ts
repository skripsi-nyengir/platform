import {
  SetSimActiveModelRequestSchema,
  SetSimActiveModelResponseSchema,
  SimModelsResponseSchema,
  type SetSimActiveModelResponse,
  type SimModelsResponse,
} from '../contracts/simulation'
import { requestJson } from './http'

export function getSimulationModels(signal?: AbortSignal): Promise<SimModelsResponse> {
  return requestJson('/api/simulation/models', SimModelsResponseSchema, { signal })
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

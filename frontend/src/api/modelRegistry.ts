import {
  ModelRegistryResponseSchema,
  type ModelRegistryResponse,
} from '../contracts/modelRegistry'
import { requestJson } from './http'

export function getModelRegistry(signal?: AbortSignal): Promise<ModelRegistryResponse> {
  return requestJson('/api/model-registry', ModelRegistryResponseSchema, { signal })
}

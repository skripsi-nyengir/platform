import {
  LivenessResponseSchema,
  ReadinessResponseSchema,
  SystemStatusResponseSchema,
  type LivenessResponse,
  type ReadinessResponse,
  type SystemStatusResponse,
} from '../contracts/systemHealth'
import { requestJson } from './http'

export function getSystemStatus(signal?: AbortSignal): Promise<SystemStatusResponse> {
  return requestJson('/api/system/status', SystemStatusResponseSchema, { signal })
}

export function getLiveness(signal?: AbortSignal): Promise<LivenessResponse> {
  return requestJson('/health', LivenessResponseSchema, { signal })
}

export function getReadiness(signal?: AbortSignal): Promise<ReadinessResponse> {
  return requestJson('/ready', ReadinessResponseSchema, { signal })
}

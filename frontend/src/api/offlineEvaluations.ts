import {
  OfflineEvaluationsResponseSchema,
  type OfflineEvaluationsResponse,
} from '../contracts/offlineEvaluations'
import { requestJson } from './http'

export function getOfflineEvaluations(signal?: AbortSignal): Promise<OfflineEvaluationsResponse> {
  return requestJson('/api/offline-evaluations', OfflineEvaluationsResponseSchema, { signal })
}

import {
  InferenceQuerySchema,
  InferenceResponseSchema,
  type InferenceQuery,
  type InferenceResponse,
} from '../contracts/inference'
import { requestJson } from './http'

export async function getInferenceResults(
  input: InferenceQuery,
  signal?: AbortSignal,
): Promise<InferenceResponse> {
  const queryInput = InferenceQuerySchema.parse(input)
  const query = new URLSearchParams({
    device_id: queryInput.deviceId,
    from: queryInput.from,
    to: queryInput.to,
    bucket: queryInput.bucket,
    limit: String(queryInput.limit),
  })
  if (queryInput.cursor !== undefined) query.set('cursor', queryInput.cursor)
  if (queryInput.modelVersion !== undefined) {
    query.set('model_version', queryInput.modelVersion)
  }
  const maximumPoints = Math.min(queryInput.limit, queryInput.bucket === 'raw' ? 5_000 : 2_000)
  const responseSchema = InferenceResponseSchema.superRefine((value, context) => {
    if (value.points.length > maximumPoints) {
      context.addIssue({
        code: 'custom',
        message: 'points length exceeds the requested response bound',
        path: ['points'],
      })
    }
  })
  return requestJson(`/api/inference-results?${query}`, responseSchema, { signal })
}

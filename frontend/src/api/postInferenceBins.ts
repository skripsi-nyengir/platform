import {
  PostInferenceBinsQuerySchema,
  PostInferenceBinsResponseSchema,
  type PostInferenceBinsQuery,
  type PostInferenceBinsResponse,
} from '../contracts/postInferenceBins'
import { requestJson } from './http'

export async function getPostInferenceBins(
  input: PostInferenceBinsQuery,
  signal?: AbortSignal,
): Promise<PostInferenceBinsResponse> {
  const queryInput = PostInferenceBinsQuerySchema.parse(input)
  const query = new URLSearchParams({
    device_id: queryInput.deviceId,
    from: queryInput.from,
    to: queryInput.to,
    limit: String(queryInput.limit),
  })
  if (queryInput.cursor !== undefined) query.set('cursor', queryInput.cursor)
  if (queryInput.modelVersion !== undefined) {
    query.set('model_version', queryInput.modelVersion)
  }
  const responseSchema = PostInferenceBinsResponseSchema.superRefine(
    (value, context) => {
      if (value.bins.length > queryInput.limit) {
        context.addIssue({
          code: 'custom',
          message: 'bins length exceeds the requested response bound',
          path: ['bins'],
        })
      }
    },
  )
  return requestJson(`/api/post-inference-bins?${query}`, responseSchema, { signal })
}

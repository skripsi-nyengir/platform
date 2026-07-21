import {
  EdaCorrelationQuerySchema,
  EdaCorrelationResponseSchema,
  EdaDistributionQuerySchema,
  EdaDistributionResponseSchema,
  EdaSummaryQuerySchema,
  EdaSummaryResponseSchema,
  type EdaCorrelationQuery,
  type EdaCorrelationResponse,
  type EdaDistributionQuery,
  type EdaDistributionResponse,
  type EdaSummaryQuery,
  type EdaSummaryResponse,
} from '../contracts/eda'
import { requestJson } from './http'

export async function getEdaSummary(
  input: EdaSummaryQuery,
  signal?: AbortSignal,
): Promise<EdaSummaryResponse> {
  const queryInput = EdaSummaryQuerySchema.parse(input)
  const query = new URLSearchParams()
  if (queryInput.deviceId !== undefined) query.set('device_id', queryInput.deviceId)
  query.set('from', queryInput.from)
  query.set('to', queryInput.to)
  query.set('bucket', queryInput.bucket)
  return requestJson(`/api/eda/summary?${query}`, EdaSummaryResponseSchema, { signal })
}

export async function getEdaDistributions(
  input: EdaDistributionQuery,
  signal?: AbortSignal,
): Promise<EdaDistributionResponse> {
  const queryInput = EdaDistributionQuerySchema.parse(input)
  const query = new URLSearchParams()
  if (queryInput.deviceId !== undefined) query.set('device_id', queryInput.deviceId)
  query.set('from', queryInput.from)
  query.set('to', queryInput.to)
  query.set('field', queryInput.field)
  query.set('bins', String(queryInput.bins))
  const responseSchema = EdaDistributionResponseSchema.superRefine((value, context) => {
    if (value.bins.length > queryInput.bins) {
      context.addIssue({
        code: 'custom',
        message: 'bins length must not exceed the requested bins',
        path: ['bins'],
      })
    }
  })
  return requestJson(`/api/eda/distributions?${query}`, responseSchema, {
    signal,
  })
}

export async function getEdaCorrelation(
  input: EdaCorrelationQuery,
  signal?: AbortSignal,
): Promise<EdaCorrelationResponse> {
  const queryInput = EdaCorrelationQuerySchema.parse(input)
  const query = new URLSearchParams()
  if (queryInput.deviceId !== undefined) query.set('device_id', queryInput.deviceId)
  query.set('from', queryInput.from)
  query.set('to', queryInput.to)
  query.set('x_field', queryInput.xField)
  query.set('y_field', queryInput.yField)
  query.set('max_points', String(queryInput.maxPoints))
  if (queryInput.cursor !== undefined) query.set('cursor', queryInput.cursor)
  const responseSchema = EdaCorrelationResponseSchema.superRefine((value, context) => {
    if (value.points.length > queryInput.maxPoints) {
      context.addIssue({
        code: 'custom',
        message: 'points length must not exceed max_points',
        path: ['points'],
      })
    }
  })
  return requestJson(`/api/eda/correlation?${query}`, responseSchema, { signal })
}

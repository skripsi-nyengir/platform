import { z } from 'zod'
import {
  ModelEvaluationDetailSchema,
  ModelEvaluationsQuerySchema,
  ModelEvaluationsResponseSchema,
  type ModelEvaluationDetail,
  type ModelEvaluationsQuery,
  type ModelEvaluationsResponse,
} from '../contracts/modelEvaluation'
import { requestJson } from './http'

const ModelVersionSchema = z.string().min(1)

export async function getModelEvaluations(
  input: ModelEvaluationsQuery = {},
  signal?: AbortSignal,
): Promise<ModelEvaluationsResponse> {
  const queryInput = ModelEvaluationsQuerySchema.parse(input)
  const query = new URLSearchParams({
    page: String(queryInput.page),
    page_size: String(queryInput.pageSize),
  })
  const responseSchema = ModelEvaluationsResponseSchema.superRefine((value, context) => {
    if (value.page !== queryInput.page || value.page_size !== queryInput.pageSize) {
      context.addIssue({
        code: 'custom',
        message: 'response pagination must match the request',
        path: ['page'],
      })
    }
  })
  return requestJson(`/api/model-evaluations?${query}`, responseSchema, {
    signal,
  })
}

export async function getModelEvaluation(
  version: string,
  signal?: AbortSignal,
): Promise<ModelEvaluationDetail> {
  const modelVersion = ModelVersionSchema.parse(version)
  return requestJson(
    `/api/model-evaluations/${encodeURIComponent(modelVersion)}`,
    ModelEvaluationDetailSchema,
    { signal },
  )
}

import {
  EdaComputeRequestSchema,
  EdaComputeResponseSchema,
  EdaJobResponseSchema,
  EdaPeriodListQuerySchema,
  EdaPeriodListResponseSchema,
  EdaRunResponseSchema,
  EdaSectionNameSchema,
  EdaSectionResponseSchema,
  type EdaComputeRequest,
  type EdaComputeResponse,
  type EdaJobResponse,
  type EdaPeriodListQuery,
  type EdaPeriodListResponse,
  type EdaRunResponse,
  type EdaSectionName,
  type EdaSectionResponse,
} from '../contracts/eda'
import { requestJson } from './http'

function requiredId(value: string, name: string): string {
  if (value.length === 0) throw new Error(`${name} is required`)
  return encodeURIComponent(value)
}

export function getEdaPeriods(
  input: EdaPeriodListQuery,
  signal?: AbortSignal,
): Promise<EdaPeriodListResponse> {
  const queryInput = EdaPeriodListQuerySchema.parse(input)
  const query = new URLSearchParams()
  query.set('period_kind', queryInput.period_kind)
  query.set('limit', String(queryInput.limit))
  if (queryInput.cursor !== null) query.set('cursor', queryInput.cursor)
  return requestJson(`/api/eda/periods?${query}`, EdaPeriodListResponseSchema, { signal })
}

export function computeEda(
  input: EdaComputeRequest,
  signal?: AbortSignal,
): Promise<EdaComputeResponse> {
  const body = EdaComputeRequestSchema.parse(input)
  return requestJson('/api/eda/compute', EdaComputeResponseSchema, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
}

export function getEdaJob(jobId: string, signal?: AbortSignal): Promise<EdaJobResponse> {
  return requestJson(
    `/api/eda/jobs/${requiredId(jobId, 'jobId')}`,
    EdaJobResponseSchema,
    { signal },
  )
}

export function getEdaRun(runId: string, signal?: AbortSignal): Promise<EdaRunResponse> {
  return requestJson(
    `/api/eda/runs/${requiredId(runId, 'runId')}`,
    EdaRunResponseSchema,
    { signal },
  )
}

export function getEdaSection(
  runId: string,
  section: EdaSectionName,
  signal?: AbortSignal,
): Promise<EdaSectionResponse> {
  const parsedSection = EdaSectionNameSchema.parse(section)
  return requestJson(
    `/api/eda/runs/${requiredId(runId, 'runId')}/sections/${parsedSection}`,
    EdaSectionResponseSchema,
    { signal },
  )
}

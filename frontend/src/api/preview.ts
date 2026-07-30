import {
  DevicesResponseSchema,
  ReplayJobRequestSchema,
  ReplayJobResponseSchema,
  ReplayJobStatusResponseSchema,
  type DevicesResponse,
  type ReplayJobRequest,
  type ReplayJobResponse,
  type ReplayJobStatusResponse,
} from '../contracts/preview'
import { requestJson } from './http'

export function getDevices(signal?: AbortSignal): Promise<DevicesResponse> {
  return requestJson('/api/devices', DevicesResponseSchema, { signal })
}

export function createReplayJob(
  input: ReplayJobRequest,
  signal?: AbortSignal,
): Promise<ReplayJobResponse> {
  const body = ReplayJobRequestSchema.parse(input)
  return requestJson('/api/replay-jobs', ReplayJobResponseSchema, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
}

export function getReplayJob(
  jobId: string,
  signal?: AbortSignal,
): Promise<ReplayJobStatusResponse> {
  if (jobId.length === 0) throw new Error('jobId is required')
  return requestJson(
    `/api/replay-jobs/${encodeURIComponent(jobId)}`,
    ReplayJobStatusResponseSchema,
    { signal },
  )
}

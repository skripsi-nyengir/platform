import { SensorIdSchema, type SensorId } from '../contracts/common'
import {
  LatestTelemetryResponseSchema,
  TelemetryHistoryQuerySchema,
  TelemetryHistoryResponseSchema,
  type LatestTelemetryResponse,
  type TelemetryHistoryQuery,
  type TelemetryHistoryResponse,
} from '../contracts/telemetry'
import { requestJson } from './http'

export async function getLatestTelemetry(
  deviceId?: SensorId,
  signal?: AbortSignal,
): Promise<LatestTelemetryResponse> {
  const query = new URLSearchParams()
  if (deviceId !== undefined) query.set('device_id', SensorIdSchema.parse(deviceId))
  const path: `/api/${string}` = query.size
    ? `/api/telemetry/latest?${query}`
    : '/api/telemetry/latest'
  return requestJson(path, LatestTelemetryResponseSchema, { signal })
}

export async function getTelemetryHistory(
  input: TelemetryHistoryQuery,
  signal?: AbortSignal,
): Promise<TelemetryHistoryResponse> {
  const queryInput = TelemetryHistoryQuerySchema.parse(input)
  const query = new URLSearchParams({
    device_id: queryInput.deviceId,
    from: queryInput.from,
    to: queryInput.to,
    bucket: queryInput.bucket,
    limit: String(queryInput.limit),
  })
  if (queryInput.cursor !== undefined) query.set('cursor', queryInput.cursor)
  const responseSchema = TelemetryHistoryResponseSchema.superRefine((value, context) => {
    if (value.points.length > queryInput.limit) {
      context.addIssue({
        code: 'custom',
        message: 'points length must not exceed the requested limit',
        path: ['points'],
      })
    }
  })
  return requestJson(`/api/telemetry/history?${query}`, responseSchema, { signal })
}

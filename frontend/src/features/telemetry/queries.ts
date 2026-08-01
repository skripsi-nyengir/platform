import { useQuery } from '@tanstack/react-query'
import { getLatestTelemetry, getTelemetryHistory } from '../../api/telemetry'
import { SensorIdSchema, type SensorId } from '../../contracts/common'
import {
  TelemetryHistoryQuerySchema,
  type TelemetryHistoryQuery,
} from '../../contracts/telemetry'
import { liveQueryOptions } from '../useLiveTelemetryData'

export function useLatestTelemetryQuery(deviceId?: SensorId) {
  const normalizedDeviceId = SensorIdSchema.optional().parse(deviceId)
  return useQuery({
    queryKey: ['telemetry', 'latest', normalizedDeviceId ?? null],
    queryFn: ({ signal }) => getLatestTelemetry(normalizedDeviceId, signal),
    ...liveQueryOptions,
  })
}

export function useTelemetryHistoryQuery(input: TelemetryHistoryQuery) {
  const query = TelemetryHistoryQuerySchema.parse(input)
  return useQuery({
    queryKey: [
      'telemetry',
      'history',
      query.deviceId,
      query.from,
      query.to,
      query.bucket,
      query.limit,
      query.cursor ?? null,
    ],
    queryFn: ({ signal }) => getTelemetryHistory(query, signal),
    ...liveQueryOptions,
  })
}

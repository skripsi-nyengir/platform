import { useQuery } from '@tanstack/react-query'
import { getCurrentAlerts, getAlertEvents } from '../api/alerts'
import { getInferenceResults } from '../api/inference'
import { getPostInferenceBins } from '../api/postInferenceBins'
import { getSystemStatus } from '../api/systemHealth'
import { getLatestTelemetry, getTelemetryHistory } from '../api/telemetry'
import { wibHistoricalDateTimeToUtcInstant, type SensorId } from '../contracts/common'
import { resolveLiveRange, type LiveUrlFilters } from './filters/urlFilters'

export const livePollIntervalMs = 3_000

export const liveQueryOptions = {
  refetchInterval: livePollIntervalMs,
  staleTime: livePollIntervalMs,
  refetchIntervalInBackground: false,
  refetchOnWindowFocus: true,
  refetchOnReconnect: true,
} as const

function rangeKey(filters: LiveUrlFilters) {
  return [filters.range, filters.from ?? null, filters.to ?? null] as const
}

export function useLiveTelemetryData(sensorId: SensorId, filters: LiveUrlFilters) {
  const semanticRange = rangeKey(filters)
  const latestTelemetry = useQuery({
    queryKey: ['live', 'telemetry-latest', sensorId],
    queryFn: ({ signal }) => getLatestTelemetry(sensorId, signal),
    ...liveQueryOptions,
  })
  const telemetryHistory = useQuery({
    queryKey: ['live', 'telemetry-history', sensorId, ...semanticRange],
    queryFn: ({ signal }) => {
      const range = resolveLiveRange(filters)
      return getTelemetryHistory({
        deviceId: sensorId,
        ...range,
        limit: range.bucket === 'raw' ? 5_000 : 2_000,
      }, signal)
    },
    ...liveQueryOptions,
  })
  const inference = useQuery({
    queryKey: [
      'live',
      'inference',
      sensorId,
      ...semanticRange,
      filters.modelVersion ?? null,
    ],
    queryFn: ({ signal }) => {
      const range = resolveLiveRange(filters)
      return getInferenceResults({
        deviceId: sensorId,
        ...range,
        limit: range.bucket === 'raw' ? 5_000 : 2_000,
        modelVersion: filters.modelVersion,
      }, signal)
    },
    ...liveQueryOptions,
  })
  const postInferenceBins = useQuery({
    queryKey: [
      'live',
      'post-inference-bins',
      sensorId,
      ...semanticRange,
      filters.modelVersion ?? null,
    ],
    queryFn: ({ signal }) => {
      const range = resolveLiveRange(filters)
      return getPostInferenceBins({
        deviceId: sensorId,
        from: range.from,
        to: range.to,
        limit: 5_000,
        modelVersion: filters.modelVersion,
      }, signal)
    },
    ...liveQueryOptions,
  })
  const currentAlerts = useQuery({
    queryKey: ['live', 'current-alerts', sensorId],
    queryFn: ({ signal }) => getCurrentAlerts({ deviceId: sensorId, page: 1, pageSize: 100 }, signal),
    ...liveQueryOptions,
  })
  const alertEvents = useQuery({
    queryKey: ['live', 'alert-events', sensorId, ...semanticRange],
    queryFn: ({ signal }) => {
      const range = resolveLiveRange(filters)
      return getAlertEvents({
        deviceId: sensorId,
        from: wibHistoricalDateTimeToUtcInstant(range.from),
        to: wibHistoricalDateTimeToUtcInstant(range.to),
        limit: 200,
      }, signal)
    },
    ...liveQueryOptions,
  })
  const health = useQuery({
    queryKey: ['live', 'health'],
    queryFn: ({ signal }) => getSystemStatus(signal),
    ...liveQueryOptions,
  })

  return { latestTelemetry, telemetryHistory, inference, postInferenceBins, currentAlerts, alertEvents, health }
}

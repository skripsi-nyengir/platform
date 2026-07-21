import type { UseQueryResult } from '@tanstack/react-query'
import { useState } from 'react'
import type { ApiError } from '../../api/errors'
import type { CurrentAlertsResponse } from '../../contracts/alerts'
import type { SensorId } from '../../contracts/common'
import type { InferenceResultsResponse } from '../../contracts/inference'
import type { LatestTelemetryResponse } from '../../contracts/telemetry'
import { useCurrentAlertsQuery } from '../alerts/queries'
import { useInferenceResultsQuery } from '../inference/queries'
import { useLatestTelemetryQuery } from '../telemetry/queries'

export interface LatestSensorScore {
  deviceId: SensorId
  score?: number
  threshold?: number
  isAnomaly?: boolean
}

function latestScore(
  deviceId: SensorId,
  response?: InferenceResultsResponse,
): LatestSensorScore {
  const point = response?.points.at(-1)
  return point === undefined
    ? { deviceId }
    : {
        deviceId,
        score: point.score,
        threshold: point.threshold,
        isAnomaly: point.is_anomaly,
      }
}

export function useOverviewData(): {
  latestTelemetry: UseQueryResult<LatestTelemetryResponse, ApiError>
  currentAlerts: UseQueryResult<CurrentAlertsResponse, ApiError>
  latestScores: readonly LatestSensorScore[]
} {
  const [range] = useState(() => {
    const to = Date.now()
    return {
      from: new Date(to - 30 * 60 * 1_000).toISOString(),
      to: new Date(to).toISOString(),
    }
  })
  const latestTelemetry = useLatestTelemetryQuery()
  const currentAlerts = useCurrentAlertsQuery({ status: 'detected', page: 1, pageSize: 100 })
  const n1 = useInferenceResultsQuery({ deviceId: 'n1', ...range, bucket: 'raw', limit: 500 })
  const n2 = useInferenceResultsQuery({ deviceId: 'n2', ...range, bucket: 'raw', limit: 500 })
  const n3 = useInferenceResultsQuery({ deviceId: 'n3', ...range, bucket: 'raw', limit: 500 })
  const n4 = useInferenceResultsQuery({ deviceId: 'n4', ...range, bucket: 'raw', limit: 500 })
  const n5 = useInferenceResultsQuery({ deviceId: 'n5', ...range, bucket: 'raw', limit: 500 })
  const n6 = useInferenceResultsQuery({ deviceId: 'n6', ...range, bucket: 'raw', limit: 500 })
  const latestScores: readonly LatestSensorScore[] = [
    latestScore('n1', n1.data),
    latestScore('n2', n2.data),
    latestScore('n3', n3.data),
    latestScore('n4', n4.data),
    latestScore('n5', n5.data),
    latestScore('n6', n6.data),
  ]

  return { latestTelemetry, currentAlerts, latestScores }
}

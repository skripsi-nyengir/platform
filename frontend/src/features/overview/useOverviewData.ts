import type { UseQueryResult } from '@tanstack/react-query'
import type { ApiError } from '../../api/errors'
import type { CurrentAlertsResponse } from '../../contracts/alerts'
import type { SensorId } from '../../contracts/common'
import { publicDeviceId } from '../../contracts/common'
import type { InferenceResultsResponse } from '../../contracts/inference'
import type { Provenance } from '../../components/data/provenance'
import type { LatestTelemetryResponse } from '../../contracts/telemetry'
import { useCurrentAlertsQuery } from '../alerts/queries'
import { telemetryDefaultRange } from '../filters/urlFilters'
import { useInferenceResultsQuery } from '../inference/queries'
import { useLatestTelemetryQuery } from '../telemetry/queries'

export interface LatestSensorScore {
  deviceId: SensorId
  score?: number
  threshold?: number
  isAnomaly?: boolean
  provenance?: Provenance
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
        provenance: point.score_provenance,
      }
}

export function useOverviewData(): {
  latestTelemetry: UseQueryResult<LatestTelemetryResponse, ApiError>
  currentAlerts: UseQueryResult<CurrentAlertsResponse, ApiError>
  latestScores: readonly LatestSensorScore[]
} {
  const latestTelemetry = useLatestTelemetryQuery()
  const currentAlerts = useCurrentAlertsQuery({ status: 'detected', page: 1, pageSize: 100 })
  const inference = useInferenceResultsQuery({
    deviceId: publicDeviceId,
    ...telemetryDefaultRange,
    bucket: 'raw',
    limit: 500,
  })
  const latestScores: readonly LatestSensorScore[] = [
    latestScore(publicDeviceId, inference.data),
  ]

  return { latestTelemetry, currentAlerts, latestScores }
}

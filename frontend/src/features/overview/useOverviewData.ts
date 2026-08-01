import type { Provenance } from '../../components/data/provenance'
import type { SensorId, Severity } from '../../contracts/common'
import type { InferenceResultsResponse } from '../../contracts/inference'

export interface LatestSensorScore {
  deviceId: SensorId
  score?: number
  threshold?: number
  isAnomaly?: boolean
  provenance?: Provenance
  severity?: Severity
}

export function latestSensorScore(
  deviceId: SensorId,
  response?: InferenceResultsResponse,
): LatestSensorScore {
  const point = response?.points.at(-1)
  return point === undefined
    ? { deviceId }
    : {
        deviceId,
        score: point.latest_score ?? point.score,
        threshold: point.threshold,
        isAnomaly: point.is_anomaly,
        provenance: point.score_provenance,
        ...(point.severity === null ? {} : { severity: point.severity }),
      }
}

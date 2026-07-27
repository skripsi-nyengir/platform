import { publicDeviceId, type SensorId } from '../../contracts/common'
import type { InferencePoint } from '../../contracts/inference'

export const previewThresholds = Object.freeze({
  [publicDeviceId]: 1,
} satisfies Record<SensorId, number>)
export const armBThresholds = previewThresholds
export const fixtureModelVersion = 'preview-lstm-ae-v1'

function inferencePoint(
  windowStart: string,
  windowEnd: string,
  score: number,
): Readonly<InferencePoint> {
  return Object.freeze({
    window_start_ts: windowStart,
    window_end_ts: windowEnd,
    score_ts: windowEnd,
    score,
    threshold: 1,
    is_anomaly: score > 1,
    model_version: fixtureModelVersion,
    score_provenance: 'simulated_preview',
  })
}

function inferenceHistory(scores: readonly number[]): readonly Readonly<InferencePoint>[] {
  const starts = [
    '2026-05-31T23:47:30',
    '2026-05-31T23:48:00',
    '2026-05-31T23:48:30',
    '2026-05-31T23:49:00',
  ]
  return Object.freeze(scores.map((score, index) =>
    inferencePoint(starts[index] ?? starts[0], `2026-05-31T23:${49 + index}:30`, score),
  ))
}

export const normalInferenceBySensor = Object.freeze({
  [publicDeviceId]: inferenceHistory([0.31, 0.45, 0.72, 0.58]),
} satisfies Record<SensorId, readonly InferencePoint[]>)

export const activeAnomalyInferenceBySensor = Object.freeze({
  [publicDeviceId]: inferenceHistory([0.31, 0.45, 1.22, 1.31]),
} satisfies Record<SensorId, readonly InferencePoint[]>)

export const normalInferencePoints = normalInferenceBySensor[publicDeviceId]
export const activeAnomalyInferencePoints = activeAnomalyInferenceBySensor[publicDeviceId]

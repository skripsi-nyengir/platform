import type { InferencePoint } from '../../contracts/inference'

export const fixtureModelVersion = 'model-v1'
export const fixtureModelHash = 'sha256:model-v1'
export const fixturePreprocessingHash = 'sha256:preprocessing-v1'
export const fixtureThresholdHash = 'sha256:threshold-v1'

function inferencePoint(
  window_start_ts: string,
  window_end_ts: string,
  score: number,
  is_anomaly = false,
): Readonly<InferencePoint> {
  return Object.freeze({
    window_start_ts,
    window_end_ts,
    score,
    threshold: 0.8,
    is_anomaly,
    model_version: fixtureModelVersion,
    model_hash: fixtureModelHash,
    preprocessing_hash: fixturePreprocessingHash,
    threshold_hash: fixtureThresholdHash,
  })
}

export const normalInferencePoints = Object.freeze([
  inferencePoint('2026-07-19T10:00:00Z', '2026-07-19T10:05:00Z', 0.18),
  inferencePoint('2026-07-19T10:05:00Z', '2026-07-19T10:10:00Z', 0.24),
  inferencePoint('2026-07-19T10:10:00Z', '2026-07-19T10:15:00Z', 0.31),
  inferencePoint('2026-07-19T10:15:00Z', '2026-07-19T10:20:00Z', 0.27),
])

export const activeAnomalyInferencePoints = Object.freeze([
  ...normalInferencePoints.slice(0, -1),
  inferencePoint('2026-07-19T10:15:00Z', '2026-07-19T10:20:00Z', 0.96, true),
])

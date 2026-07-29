import { simDeviceId } from '../../contracts/common'
import type { InferencePoint } from '../../contracts/inference'
import type { SimInjectionEvent } from '../../contracts/injection'
import type { SimModelsResponse } from '../../contracts/simulation'
import type { TelemetryPoint } from '../../contracts/telemetry'

const modelDefinitions = [
  {
    version: 'artifact-lstm-ae-v3',
    model_key: 'artifact-lstm-ae',
    display_name: 'LSTM-AE',
    score_key: 'global_mse',
    threshold: 0.0006799018211313575,
    manifest_sha256: 'f26a67d378c4b5a90e64f7dc3844d2971cb414d1bf60926fefa188b13df99212',
  },
  {
    version: 'artifact-conv1d-v3',
    model_key: 'artifact-conv1d',
    display_name: 'Conv1D Autoencoder',
    score_key: 'global_mse',
    threshold: 0.00033055954801966444,
    manifest_sha256: '189a935b547163d00505deb4f654d59ca36d7077e54b87f4b5c472cf41c5fcc6',
  },
  {
    version: 'artifact-transformer-v3',
    model_key: 'artifact-transformer',
    display_name: 'Transformer Autoencoder',
    score_key: 'global_mse',
    threshold: 0.0003650374799326533,
    manifest_sha256: '21ec02b261b64f4491f0e5ecac1cbc41cba55fb7cb07d85b0596ca467e213b3b',
  },
] as const

export function simulationModelsResponse(activeModelVersion: string): SimModelsResponse {
  return {
    request_id: 'req_simulation_models',
    device_id: simDeviceId,
    models: modelDefinitions.map((model) => ({
      ...model,
      is_active: model.version === activeModelVersion,
    })),
  }
}

export const simulationInjectionEvents = Object.freeze([
  {
    event_id: 'injection-spike-001',
    family: 'spike',
    severity: 'high',
    channel: 'suhu',
    channel_index: 0,
    start_ts: '2026-04-19T00:54:36',
    end_ts: '2026-04-19T00:58:08',
    start_idx: 51,
    end_idx_exclusive: 89,
    segment_index: 0,
  },
  {
    event_id: 'injection-drift-002',
    family: 'drift',
    severity: 'medium',
    channel: 'rh',
    channel_index: 1,
    start_ts: '2026-04-19T01:18:00',
    end_ts: '2026-04-19T01:22:00',
    start_idx: 290,
    end_idx_exclusive: 333,
    segment_index: 0,
  },
  {
    event_id: 'injection-loss-003',
    family: 'data_loss',
    severity: 'low',
    channel: 'suhu',
    channel_index: 0,
    start_ts: '2026-04-19T01:35:00',
    end_ts: '2026-04-19T01:38:00',
    start_idx: 470,
    end_idx_exclusive: 503,
    segment_index: 0,
  },
] satisfies SimInjectionEvent[])

const simulationTelemetryValues = [
  ['2026-04-19T00:49:45', 27.04, 49.17],
  ['2026-04-19T00:55:00', 29.82, 49.04],
  ['2026-04-19T00:58:00', 27.31, 49.22],
  ['2026-04-19T01:18:00', 27.11, 55.9],
  ['2026-04-19T01:22:00', 27.08, 61.4],
  ['2026-04-19T01:36:00', 26.97, 50.2],
  ['2026-04-19T01:49:00', 27.01, 49.8],
] as const

export const simulationTelemetryPoints = Object.freeze(simulationTelemetryValues.map(([
  ts,
  temperature_c,
  relative_humidity_pct,
]) => ({
  ts,
  temperature_c,
  relative_humidity_pct,
  sample_count: 1,
  gap_before: false,
})) satisfies readonly TelemetryPoint[])

export function simulationInferencePoints(modelVersion: string): readonly InferencePoint[] {
  const threshold = modelDefinitions.find((model) => model.version === modelVersion)?.threshold ?? modelDefinitions[0].threshold
  const values = [
    ['2026-04-19T00:53:00', '2026-04-19T00:55:00', threshold * 1.4],
    ['2026-04-19T00:56:00', '2026-04-19T00:58:00', threshold * 1.2],
    ['2026-04-19T01:18:00', '2026-04-19T01:20:00', threshold * 0.6],
    ['2026-04-19T01:19:00', '2026-04-19T01:21:00', threshold * 1.3],
    ['2026-04-19T01:28:00', '2026-04-19T01:30:00', threshold * 1.1],
    ['2026-04-19T01:35:00', '2026-04-19T01:37:00', threshold * 0.5],
    ['2026-04-19T01:43:00', '2026-04-19T01:45:00', threshold * 0.4],
  ] as const
  return values.map(([window_start_ts, window_end_ts, score]) => ({
    window_start_ts,
    window_end_ts,
    score_ts: window_end_ts,
    score,
    threshold,
    is_anomaly: score > threshold,
    model_version: modelVersion,
    score_provenance: 'artifact_backed',
  }))
}

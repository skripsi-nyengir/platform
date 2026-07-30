import { simDeviceId } from '../../contracts/common'
import type { InferencePoint } from '../../contracts/inference'
import type { SimInjectionEvent } from '../../contracts/injection'
import {
  simModelWindowSizes,
  type SimulationMetricsResponse,
  type SimulationScopeMetrics,
  type SimModelVersion,
  type SimModelsResponse,
} from '../../contracts/simulation'
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
  {
    version: 'artifact-gru-v3',
    model_key: 'artifact-gru',
    display_name: 'GRU-AE',
    score_key: 'global_mse',
    threshold: 0.0005618056084495022,
    manifest_sha256: '0506d1da27d92a259e62c32ce43db7fd19dfa8ad679c08c6d67bf727653a2caa',
  },
  {
    version: 'artifact-rnn-v3',
    model_key: 'artifact-rnn',
    display_name: 'RNN-AE',
    score_key: 'global_mse',
    threshold: 0.0005023972923204374,
    manifest_sha256: 'c801a284c95c16ce9031a24f774d941c314bc0758e7b20d593af64fb630f0ebd',
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

const injectionFamilies = ['spike', 'drift', 'stuck', 'erratic', 'bias', 'data_loss', 'garbage'] as const
const injectionSeverities = ['low', 'medium', 'high'] as const
const injectionCorpusStart = Date.parse('2026-04-19T00:54:36Z')

export const simulationInjectionEvents = Object.freeze(Array.from({ length: 210 }, (_, index) => {
  const start = new Date(injectionCorpusStart + index * 51 * 60 * 1_000)
  const end = new Date(start.getTime() + 3 * 60 * 1_000 + 32 * 1_000)
  return {
    event_id: `injection-${String(index + 1).padStart(3, '0')}`,
    family: injectionFamilies[index % injectionFamilies.length],
    severity: injectionSeverities[index % injectionSeverities.length],
    channel: index % 2 === 0 ? 'suhu' : 'rh',
    channel_index: index % 2,
    start_ts: start.toISOString().slice(0, 19),
    end_ts: end.toISOString().slice(0, 19),
    start_idx: index * 500 + 48,
    end_idx_exclusive: index * 500 + 84,
    segment_index: Math.floor(index / 12),
  }
}) satisfies SimInjectionEvent[])

function scope<T extends 'timestamp' | 'overlapping_model_windows' | 'non_overlapping_evaluation_bins'>(
  name: T,
  values: readonly [number, number, number, number, number, number, number],
): Omit<SimulationScopeMetrics, 'scope'> & { scope: T } {
  const [precision, recall, f1, tn, fp, fn, tp] = values
  const nEvaluated = tn + fp + fn + tp
  return {
    scope: name,
    precision,
    recall,
    f1,
    accuracy: (tn + tp) / nEvaluated,
    tn,
    fp,
    fn,
    tp,
    n_evaluated: nEvaluated,
    n_anomalous: fn + tp,
  }
}

export function simulationMetricsResponse(
  modelVersion: SimModelVersion,
  bucketHours: number | null = null,
): SimulationMetricsResponse {
  const model = modelDefinitions.find((candidate) => candidate.version === modelVersion)
  if (model === undefined) throw new Error(`Missing simulation model fixture: ${modelVersion}`)
  const operationalEvents = [
    { segment_id: 0, start_idx: 51, end_idx: 88, n_candidates: 38, peak_score: model.threshold * 2.1 },
    { segment_id: 4, start_idx: 20_112, end_idx: 20_164, n_candidates: 53, peak_score: model.threshold * 3.4 },
  ]
  const firstBucketStart = Date.parse('2026-04-19T00:00:00Z')
  const operationalBuckets = bucketHours === null ? [] : [2, 0].map((eventCount, index) => ({
    bucket_start: new Date(firstBucketStart + index * bucketHours * 3_600_000).toISOString().slice(0, 19),
    bucket_end: new Date(firstBucketStart + (index + 1) * bucketHours * 3_600_000).toISOString().slice(0, 19),
    event_count: eventCount,
  }))
  return {
    request_id: 'req_simulation_metrics',
    device_id: simDeviceId,
    model_version: modelVersion,
    threshold: model.threshold,
    window_size: simModelWindowSizes[modelVersion],
    frame_count: 105_767,
    event_count: simulationInjectionEvents.length,
    scored_windows: 105_237,
    timestamp_scope: scope('timestamp', [0.52, 0.66, 0.58, 88_810, 6_372, 3_550, 7_027]),
    overlapping_scope: scope('overlapping_model_windows', [0.64, 0.77, 0.7, 81_577, 7_224, 3_741, 12_695]),
    bins_scope: scope('non_overlapping_evaluation_bins', [0.69, 0.8, 0.74, 1_552, 153, 85, 334]),
    operational_event_count: operationalEvents.length,
    operational_events: operationalEvents,
    bucket_hours: bucketHours,
    operational_buckets: operationalBuckets,
  }
}

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
  const reconstruction = {
    'artifact-lstm-ae-v3': { values: [27.12, 27.18, 27.1, 27.09, 27.05, 27, 27.01], halfBand: 0.28 },
    'artifact-conv1d-v3': { values: [27.08, 27.2, 27.13, 27.1, 27.07, 27.02, 27.03], halfBand: 0.22 },
    'artifact-transformer-v3': { values: [27.15, 27.21, 27.12, 27.11, 27.08, 27.04, 27.02], halfBand: 0.34 },
  }[modelVersion] ?? { values: [27.12, 27.18, 27.1, 27.09, 27.05, 27, 27.01], halfBand: 0.28 }
  const values = [
    ['2026-04-19T00:53:00', '2026-04-19T00:55:00', threshold * 1.4],
    ['2026-04-19T00:56:00', '2026-04-19T00:58:00', threshold * 1.2],
    ['2026-04-19T01:18:00', '2026-04-19T01:20:00', threshold * 0.6],
    ['2026-04-19T01:19:00', '2026-04-19T01:21:00', threshold * 1.3],
    ['2026-04-19T01:28:00', '2026-04-19T01:30:00', threshold * 1.1],
    ['2026-04-19T01:35:00', '2026-04-19T01:37:00', threshold * 0.5],
    ['2026-04-19T01:43:00', '2026-04-19T01:45:00', threshold * 0.4],
  ] as const
  return values.map(([window_start_ts, window_end_ts, score], index) => ({
    window_start_ts,
    window_end_ts,
    score_ts: window_end_ts,
    score,
    threshold,
    is_anomaly: score > threshold,
    model_version: modelVersion,
    score_provenance: 'artifact_backed',
    recon_temperature_c: reconstruction.values[index] ?? null,
    recon_relative_humidity_pct: null,
    band_half_temperature_c: reconstruction.halfBand,
    band_half_relative_humidity_pct: null,
  }))
}

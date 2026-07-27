import type {
  LivenessResponse,
  ReadinessResponse,
  SystemStatusResponse,
} from '../../contracts/systemHealth'
import { fixtureGeneratedAt } from './telemetry'

const checkedAt = '2026-07-24T08:00:00Z'

export const systemStatus = Object.freeze({
  request_id: 'req_system_status',
  checked_at: checkedAt,
  overall_observation: 'Preview replay siap; artifact asli seluruh keluarga masih pending',
  services: [
    {
      name: 'API/DB',
      liveness: 'alive',
      readiness: 'ready',
      checked_at: checkedAt,
      detail: 'API dapat menjangkau database',
    },
    {
      name: 'Import telemetri nyata',
      liveness: 'alive',
      readiness: 'ready',
      checked_at: checkedAt,
      detail: 'Corpus B02F3872 sudah dipublikasikan',
    },
    {
      name: 'Preview worker',
      liveness: 'alive',
      readiness: 'ready',
      checked_at: checkedAt,
      detail: 'Worker simulator tersedia tanpa GPU',
    },
    {
      name: 'Active selection',
      liveness: 'alive',
      readiness: 'ready',
      checked_at: checkedAt,
      detail: 'preview-lstm-ae-v1 dipilih',
    },
    {
      name: 'Artifact asli',
      liveness: 'unknown',
      readiness: 'not_ready',
      checked_at: checkedAt,
      detail: 'Tujuh keluarga berstatus pending',
    },
  ],
  telemetry: {
    latest_ts: fixtureGeneratedAt,
    age_seconds: 0,
    fresh_sensor_count: 1,
    stale_sensor_count: 0,
    offline_sensor_count: 0,
  },
  diagnostics: { score_provenance: 'simulated_preview', artifact_ready_count: 0 },
} satisfies SystemStatusResponse)

export const livenessResponse = Object.freeze({
  status: 'alive',
  request_id: 'req_health',
  checked_at: checkedAt,
} satisfies LivenessResponse)

export const readinessResponse = Object.freeze({
  status: 'ready',
  request_id: 'req_ready',
  checked_at: checkedAt,
  dependencies: [
    { name: 'database', status: 'ready', detail: 'Connected' },
    { name: 'preview-worker', status: 'ready', detail: 'Simulator available' },
    { name: 'artifact', status: 'not_ready', detail: 'Pending; not required for preview replay' },
  ],
} satisfies ReadinessResponse)

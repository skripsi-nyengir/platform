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
  overall_observation: 'Live telemetry is healthy.',
  services: [
    {
      name: 'api',
      liveness: 'alive',
      readiness: 'ready',
      checked_at: checkedAt,
      detail: 'API request handling observed',
    },
    {
      name: 'database',
      liveness: 'alive',
      readiness: 'ready',
      checked_at: checkedAt,
      detail: 'Database connectivity and current revision observed',
    },
    {
      name: 'live-subscriber',
      liveness: 'alive',
      readiness: 'ready',
      checked_at: checkedAt,
      detail: 'Live subscriber lease, broker connection, and model are ready',
    },
    {
      name: 'preview-worker',
      liveness: 'alive',
      readiness: 'ready',
      checked_at: checkedAt,
      detail: 'Heartbeat worker preview teramati',
    },
    {
      name: 'active-selection',
      liveness: 'alive',
      readiness: 'ready',
      checked_at: checkedAt,
      detail: 'preview-lstm-ae-v1 dipilih untuk replay berikutnya',
    },
  ],
  telemetry: {
    classification: 'healthy',
    reasons: [],
    configuration_valid: true,
    lease_active: true,
    fencing_token: 7,
    database_heartbeat: checkedAt,
    connection_state: 'subscribed',
    connack_received: true,
    suback_received: true,
    latest_ts: fixtureGeneratedAt,
    last_valid_reading_ts: fixtureGeneratedAt,
    last_valid_reading_at: checkedAt,
    age_seconds: 0,
    last_gap_at: null,
    invalid_message_count: 0,
    retained_message_count: 0,
    last_persistence_failure_at: null,
    ingress_queue_depth: 0,
    dropped_newest_count: 0,
    pending_boundary_count: 0,
    durable_backlog_count: 0,
    cursor_ts: fixtureGeneratedAt,
    cursor_id: 'telemetry-live-1',
    recovery_ready: true,
    active_model_version: 'preview-lstm-ae-v1',
    active_scaler_corpus_id: 'b02-live',
    artifact_hashes: { model: 'mock-model-sha256' },
    retry_state: 'idle',
    fresh_sensor_count: 1,
    stale_sensor_count: 0,
    offline_sensor_count: 0,
  },
  diagnostics: { score_provenance: 'simulated_preview' },
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

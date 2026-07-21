import type {
  LivenessResponse,
  ReadinessResponse,
  SystemStatusResponse,
} from '../../contracts/systemHealth'
import { fixtureGeneratedAt } from './telemetry'

export const systemStatus = Object.freeze({
  request_id: 'req_system_status',
  checked_at: fixtureGeneratedAt,
  overall_observation: 'All deterministic mock services are ready',
  services: [
    {
      name: 'api',
      liveness: 'alive',
      readiness: 'ready',
      checked_at: fixtureGeneratedAt,
      detail: 'API is serving deterministic fixtures',
    },
    {
      name: 'database',
      liveness: 'alive',
      readiness: 'ready',
      checked_at: fixtureGeneratedAt,
      detail: 'Fixture store is ready',
    },
    {
      name: 'inference-worker',
      liveness: 'alive',
      readiness: 'ready',
      checked_at: fixtureGeneratedAt,
      detail: 'Model artifact model-v1 is loaded',
    },
  ],
  telemetry: {
    latest_ts: '2026-07-19T10:29:40Z',
    age_seconds: 20,
    fresh_sensor_count: 6,
    stale_sensor_count: 0,
    offline_sensor_count: 0,
  },
  diagnostics: { fixture_revision: 'task-3', deterministic: true },
} satisfies SystemStatusResponse)

export const livenessResponse = Object.freeze({
  status: 'alive',
  request_id: 'req_health',
  checked_at: fixtureGeneratedAt,
} satisfies LivenessResponse)

export const readinessResponse = Object.freeze({
  status: 'ready',
  request_id: 'req_ready',
  checked_at: fixtureGeneratedAt,
  dependencies: [
    { name: 'database', status: 'ready', detail: 'Fixture store is ready' },
    { name: 'model-artifact', status: 'ready', detail: 'model-v1 is loaded' },
  ],
} satisfies ReadinessResponse)

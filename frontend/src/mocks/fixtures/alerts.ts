import type { AlertEvent, CurrentAlert } from '../../contracts/alerts'
import { publicDeviceId } from '../../contracts/common'
import { fixtureModelVersion } from './inference'

export const activeAlertDetectedEvent = Object.freeze({
  event_id: 'event_b02_preview_detected',
  alert_id: 'alert_b02_preview_active',
  event_at: '2026-06-01T00:00:05Z',
  event_type: 'detected',
  device_id: publicDeviceId,
  actor: 'preview-worker',
  note: null,
  accepted_at: '2026-06-01T00:00:05Z',
  inference_model_version: fixtureModelVersion,
  detection_basis: 'simulated_preview',
} satisfies AlertEvent)

export const activeAlertSeedEvents = Object.freeze([activeAlertDetectedEvent])

export const activeDetectedAlert = Object.freeze({
  alert_id: 'alert_b02_preview_active',
  device_id: publicDeviceId,
  status: 'detected',
  episode_start_ts: '2026-05-31T23:51:30',
  episode_end_ts: '2026-05-31T23:52:30',
  last_score_ts: '2026-05-31T23:52:30',
  created_at: '2026-06-01T00:00:05Z',
  latest_event_at: activeAlertDetectedEvent.event_at,
  latest_event_id: activeAlertDetectedEvent.event_id,
  peak_score: 1.31,
  latest_score: 1.31,
  anomalous_window_count: 3,
  replay_job_id: 'replay-preview-001',
  threshold: 1,
  model_version: fixtureModelVersion,
  detection_basis: 'simulated_preview',
  can_acknowledge: true,
  can_resolve: false,
} satisfies CurrentAlert)

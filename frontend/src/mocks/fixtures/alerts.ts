import type { AlertEvent, CurrentAlert } from '../../contracts/alerts'
import { fixtureModelVersion } from './inference'

export const activeAlertDetectedEvent = Object.freeze({
  event_id: 'event_n4_detected',
  alert_id: 'alert_n4_active',
  event_ts: '2026-07-19T10:20:00Z',
  event_type: 'detected',
  device_id: 'n4',
  actor: 'inference-worker',
  note: null,
  inference_result_window_start_ts: '2026-07-19T10:15:00Z',
  inference_result_window_end_ts: '2026-07-19T10:20:00Z',
  inference_model_version: fixtureModelVersion,
} satisfies AlertEvent)

export const activeAlertSeedEvents = Object.freeze([activeAlertDetectedEvent])

export const activeDetectedAlert = Object.freeze({
  alert_id: 'alert_n4_active',
  device_id: 'n4',
  status: 'detected',
  detected_at: activeAlertDetectedEvent.event_ts,
  latest_event_ts: activeAlertDetectedEvent.event_ts,
  latest_event_id: activeAlertDetectedEvent.event_id,
  score: 0.96,
  threshold: 0.8,
  model_version: fixtureModelVersion,
  can_acknowledge: true,
  can_resolve: false,
} satisfies CurrentAlert)

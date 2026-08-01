import { publicDeviceId, type SensorId } from '../../contracts/common'
import type { PostInferenceBin } from '../../contracts/postInferenceBins'

function bin(
  ordinal: number,
  start: string,
  end: string,
  isAlert: boolean,
): Readonly<PostInferenceBin> {
  return Object.freeze({
    segment_id: 0,
    bin_ordinal: ordinal,
    start_score_ts: start,
    end_score_ts: end,
    scored_timestamp_count: 51,
    is_alert: isAlert,
    candidate_alert_count: isAlert ? 3 : 0,
    first_alert_ts: isAlert ? start : null,
    last_alert_ts: isAlert ? end : null,
    peak_score: isAlert ? 1.4 : 0.6,
    latest_score: isAlert ? 1.1 : 0.5,
    threshold: 1,
    schema_version: 'post-inference-bins-v1',
  })
}

export const normalPostInferenceBinsBySensor = Object.freeze({
  [publicDeviceId]: Object.freeze([
    bin(0, '2026-05-31T23:47:30', '2026-05-31T23:49:30', false),
    bin(1, '2026-05-31T23:50:00', '2026-05-31T23:52:00', false),
    bin(2, '2026-05-31T23:52:30', '2026-05-31T23:54:30', true),
  ]),
} satisfies Record<SensorId, readonly PostInferenceBin[]>)

export const alertPostInferenceBinsBySensor = Object.freeze({
  [publicDeviceId]: Object.freeze([
    bin(0, '2026-05-31T23:47:30', '2026-05-31T23:49:30', true),
    bin(1, '2026-05-31T23:50:00', '2026-05-31T23:52:00', true),
    bin(2, '2026-05-31T23:52:30', '2026-05-31T23:54:30', true),
  ]),
} satisfies Record<SensorId, readonly PostInferenceBin[]>)

export const normalPostInferenceBins = normalPostInferenceBinsBySensor[publicDeviceId]
export const alertPostInferenceBins = alertPostInferenceBinsBySensor[publicDeviceId]

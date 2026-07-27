import { publicDeviceId, type SensorId } from '../../contracts/common'
import type {
  LatestTelemetrySensor,
  TelemetryPoint,
} from '../../contracts/telemetry'

export const fixtureGeneratedAt = '2026-05-31T23:59:59'

export const latestTelemetrySensors = Object.freeze([
  {
    device_id: publicDeviceId,
    ts: fixtureGeneratedAt,
    temperature_c: 24.6772,
    relative_humidity_pct: 54.7147,
    freshness: 'fresh',
    age_seconds: 0,
    availability: 'online',
  },
] satisfies LatestTelemetrySensor[])

export const staleTelemetrySensor = Object.freeze({
  ...latestTelemetrySensors[0],
  ts: '2026-05-31T22:00:00',
  freshness: 'stale',
  age_seconds: 7_199,
} satisfies LatestTelemetrySensor)

export const offlineTelemetrySensor = Object.freeze({
  ...latestTelemetrySensors[0],
  ts: null,
  temperature_c: null,
  relative_humidity_pct: null,
  freshness: 'unknown',
  age_seconds: null,
  availability: 'offline',
} satisfies LatestTelemetrySensor)

function telemetryPoint(
  ts: string,
  temperature_c: number,
  relative_humidity_pct: number,
  gap_before = false,
): Readonly<TelemetryPoint> {
  return Object.freeze({
    ts,
    temperature_c,
    relative_humidity_pct,
    sample_count: 1,
    gap_before,
  })
}

const normalPoints = Object.freeze([
  telemetryPoint('2026-05-31T23:50:35', 24.5567, 50.5643),
  telemetryPoint('2026-05-31T23:50:42', 24.5567, 50.7169),
  telemetryPoint('2026-05-31T23:50:47', 24.5567, 50.5643),
  telemetryPoint('2026-05-31T23:50:54', 24.5781, 50.4575),
  telemetryPoint('2026-05-31T23:51:00', 24.5781, 50.3889),
  telemetryPoint('2026-05-31T23:51:07', 24.5781, 50.3431),
])

const gapPoints = Object.freeze([
  telemetryPoint('2026-05-31T20:24:37', 25.3958, 42.3322),
  telemetryPoint('2026-05-31T20:24:43', 25.3958, 42.0118),
  telemetryPoint('2026-05-31T20:57:48', 23.2186, 58.7888, true),
  telemetryPoint('2026-05-31T20:57:56', 23.2293, 58.7736),
])

export const telemetryHistoryBySensor = Object.freeze({
  [publicDeviceId]: normalPoints,
} satisfies Record<SensorId, readonly TelemetryPoint[]>)

export const dataGapTelemetryHistoryBySensor = Object.freeze({
  [publicDeviceId]: gapPoints,
} satisfies Record<SensorId, readonly TelemetryPoint[]>)

export const telemetryHistoryPoints = normalPoints
export const dataGapTelemetryHistoryPoints = gapPoints

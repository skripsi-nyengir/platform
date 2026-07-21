import type { SensorId } from '../../contracts/common'
import type {
  LatestTelemetrySensor,
  TelemetryPoint,
} from '../../contracts/telemetry'

export const fixtureGeneratedAt = '2026-07-19T10:30:00Z'

function latestSensor(
  device_id: SensorId,
  temperature_c: number,
  relative_humidity_pct: number,
): Readonly<LatestTelemetrySensor> {
  return Object.freeze({
    device_id,
    ts: '2026-07-19T10:29:40Z',
    temperature_c,
    relative_humidity_pct,
    freshness: 'fresh',
    age_seconds: 20,
    availability: 'online',
  })
}

export const latestTelemetrySensors = Object.freeze([
  latestSensor('n1', 24.1, 65.2),
  latestSensor('n2', 24.8, 66.1),
  latestSensor('n3', 25.2, 64.8),
  latestSensor('n4', 25.9, 63.9),
  latestSensor('n5', 24.5, 67.3),
  latestSensor('n6', 23.9, 68.1),
])

export const staleTelemetrySensor = Object.freeze({
  device_id: 'n2',
  ts: '2026-07-19T10:20:00Z',
  temperature_c: 24.6,
  relative_humidity_pct: 66.4,
  freshness: 'stale',
  age_seconds: 600,
  availability: 'online',
} satisfies LatestTelemetrySensor)

export const offlineTelemetrySensor = Object.freeze({
  device_id: 'n3',
  ts: '2026-07-19T09:30:00Z',
  temperature_c: null,
  relative_humidity_pct: null,
  freshness: 'unknown',
  age_seconds: 3_600,
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
    sample_count: 5,
    gap_before,
  })
}

export const telemetryHistoryPoints = Object.freeze([
  telemetryPoint('2026-07-19T10:00:00Z', 24.0, 65.0),
  telemetryPoint('2026-07-19T10:05:00Z', 24.2, 64.8),
  telemetryPoint('2026-07-19T10:10:00Z', 24.4, 64.6),
  telemetryPoint('2026-07-19T10:15:00Z', 24.5, 64.4),
  telemetryPoint('2026-07-19T10:20:00Z', 24.7, 64.2),
  telemetryPoint('2026-07-19T10:25:00Z', 24.8, 64.0),
])

export const dataGapTelemetryHistoryPoints = Object.freeze([
  telemetryPoint('2026-07-19T10:00:00Z', 24.0, 65.0),
  telemetryPoint('2026-07-19T10:05:00Z', 24.2, 64.8),
  telemetryPoint('2026-07-19T10:15:00Z', 24.5, 64.4, true),
  telemetryPoint('2026-07-19T10:20:00Z', 24.7, 64.2),
  telemetryPoint('2026-07-19T10:25:00Z', 24.8, 64.0),
])

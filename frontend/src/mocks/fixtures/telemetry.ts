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

const corpusStart = Date.parse('2026-02-01T00:00:00Z')
const normalPoints = Object.freeze(Array.from({ length: 2_001 }, (_, index) =>
  telemetryPoint(
    new Date(corpusStart + index * 15 * 60_000).toISOString().slice(0, 19),
    24 + Math.sin(index / 96),
    52 + Math.cos(index / 96),
  ),
))
const dailyPoints = Object.freeze(Array.from({ length: 120 }, (_, index) =>
  telemetryPoint(
    new Date(corpusStart + index * 24 * 60 * 60_000).toISOString().slice(0, 19),
    24 + Math.sin(index / 6),
    52 + Math.cos(index / 6),
  ),
))

const gapPoints = Object.freeze([
  telemetryPoint('2026-05-31T20:24:37', 25.3958, 42.3322),
  telemetryPoint('2026-05-31T20:24:43', 25.3958, 42.0118),
  telemetryPoint('2026-05-31T20:57:48', 23.2186, 58.7888, true),
  telemetryPoint('2026-05-31T20:57:56', 23.2293, 58.7736),
])

export const telemetryHistoryBySensor = Object.freeze({
  [publicDeviceId]: normalPoints,
} satisfies Record<SensorId, readonly TelemetryPoint[]>)

export const dailyTelemetryHistoryBySensor = Object.freeze({
  [publicDeviceId]: dailyPoints,
} satisfies Record<SensorId, readonly TelemetryPoint[]>)

export const dataGapTelemetryHistoryBySensor = Object.freeze({
  [publicDeviceId]: gapPoints,
} satisfies Record<SensorId, readonly TelemetryPoint[]>)

export const telemetryHistoryPoints = normalPoints
export const dataGapTelemetryHistoryPoints = gapPoints

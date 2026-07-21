import type { SensorId } from '../../contracts/common'
import type {
  CorrelationPoint,
  DistributionSummary,
  EdaField,
  MissingnessSummary,
  SensorComparison,
} from '../../contracts/eda'

function sensorComparison(
  device_id: SensorId,
  temperatureMean: number,
  humidityMean: number,
): Readonly<SensorComparison> {
  return Object.freeze({
    device_id,
    sample_count: 6,
    coverage_pct: 100,
    temperature_c: { mean: temperatureMean, p05: temperatureMean - 1, p95: temperatureMean + 1 },
    relative_humidity_pct: { mean: humidityMean, p05: humidityMean - 2, p95: humidityMean + 2 },
  })
}

export const edaMissingness = Object.freeze([
  Object.freeze({ field: 'temperature_c', missing_count: 0, missing_pct: 0 }),
  Object.freeze({ field: 'relative_humidity_pct', missing_count: 0, missing_pct: 0 }),
  Object.freeze({ field: 'score', missing_count: 0, missing_pct: 0 }),
] satisfies readonly MissingnessSummary[])

export const edaSensorComparisons = Object.freeze([
  sensorComparison('n1', 24.2, 65),
  sensorComparison('n2', 24.8, 66),
  sensorComparison('n3', 25.2, 65),
  sensorComparison('n4', 25.8, 64),
  sensorComparison('n5', 24.5, 67),
  sensorComparison('n6', 23.9, 68),
])

export const distributionSummaries = Object.freeze({
  temperature_c: Object.freeze({ min: 22, max: 28, mean: 25, median: 25, p05: 23, p95: 27 }),
  relative_humidity_pct: Object.freeze({
    min: 60,
    max: 72,
    mean: 66,
    median: 66,
    p05: 61,
    p95: 71,
  }),
  score: Object.freeze({ min: 0, max: 1, mean: 0.3, median: 0.25, p05: 0.05, p95: 0.7 }),
} satisfies Record<EdaField, DistributionSummary>)

function correlationPoint(
  device_id: SensorId,
  x: number,
  y: number,
  score: number,
): Readonly<CorrelationPoint> {
  return Object.freeze({
    ts: '2026-07-19T10:25:00Z',
    device_id,
    x,
    y,
    score,
    is_candidate_outlier: false,
  })
}

export const edaCorrelationPoints = Object.freeze([
  correlationPoint('n1', 24.2, 65, 0.18),
  correlationPoint('n2', 24.8, 66, 0.24),
  correlationPoint('n3', 25.2, 65, 0.31),
  correlationPoint('n4', 25.8, 64, 0.27),
  correlationPoint('n5', 24.5, 67, 0.2),
  correlationPoint('n6', 23.9, 68, 0.15),
])

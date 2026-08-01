import type { Theme } from '@mui/material/styles'
import type { AlertEvent } from '../../contracts/alerts'
import { historicalDateTimeToDate, sensorLabels, type SensorId } from '../../contracts/common'
import type { InferencePoint } from '../../contracts/inference'
import type { TelemetryPoint } from '../../contracts/telemetry'

export interface TemporalChartInput {
  theme: Theme
  sensorId: SensorId
  from: string
  to: string
  telemetry: readonly TelemetryPoint[]
  inference: readonly InferencePoint[]
  alerts: readonly AlertEvent[]
}

export interface OverviewSparklineInput {
  theme: Theme
  sensorId: SensorId
  from: string
  to: string
  telemetry: readonly TelemetryPoint[]
}

export interface NullableTemporalChartPoint {
  x: Date
  y: number | null
}

export interface TemporalScoreChartPoint {
  x: Date
  y: number
}

export interface TemporalAnomalyInterval {
  start: Date
  end: Date
}

export interface TemporalChartData {
  temperature: NullableTemporalChartPoint[]
  humidity: NullableTemporalChartPoint[]
  scores: TemporalScoreChartPoint[]
  threshold: number | undefined
  anomalyIntervals: TemporalAnomalyInterval[]
}

export interface OverviewSparklineData {
  temperature: NullableTemporalChartPoint[]
  humidity: NullableTemporalChartPoint[]
}

function buildTelemetryChartData(telemetry: readonly TelemetryPoint[]): OverviewSparklineData {
  const temperature: NullableTemporalChartPoint[] = []
  const humidity: NullableTemporalChartPoint[] = []

  for (const point of telemetry) {
    const x = historicalDateTimeToDate(point.ts)
    if (point.gap_before) {
      temperature.push({ x, y: null })
      humidity.push({ x, y: null })
    }
    temperature.push({ x, y: point.temperature_c })
    humidity.push({ x, y: point.relative_humidity_pct })
  }

  return { temperature, humidity }
}

export function buildTemporalChartData(input: TemporalChartInput): TemporalChartData {
  return {
    ...buildTelemetryChartData(input.telemetry),
    scores: input.inference.map((point) => ({
      x: historicalDateTimeToDate(point.score_ts),
      y: point.score,
    })),
    threshold: input.inference[0]?.threshold,
    anomalyIntervals: input.inference
      .filter((point) => point.is_anomaly)
      .map((point) => ({
        start: historicalDateTimeToDate(point.window_start_ts),
        end: historicalDateTimeToDate(point.window_end_ts),
      })),
  }
}

export function buildOverviewSparklineData(input: OverviewSparklineInput): OverviewSparklineData {
  return buildTelemetryChartData(input.telemetry)
}

export function buildTemporalSummary(input: TemporalChartInput): string {
  const gapCount = input.telemetry.filter((point) => point.gap_before).length
  const threshold = input.inference[0]?.threshold
  const anomalyCount = input.inference.filter((point) => point.is_anomaly).length
  const alertCount = input.alerts.filter((event) => event.event_type === 'detected').length

  return [
    `Sensor ${sensorLabels[input.sensorId]} from ${input.from} to ${input.to}.`,
    `${gapCount} documented gap${gapCount === 1 ? '' : 's'}.`,
    threshold === undefined ? 'Score threshold unavailable.' : `Score threshold ${threshold}.`,
    `${anomalyCount} anomaly interval${anomalyCount === 1 ? '' : 's'}.`,
    `${alertCount} detected alert${alertCount === 1 ? '' : 's'}.`,
  ].join(' ')
}

export interface ReconstructionSlicePoint {
  x: Date
  ts: string
  actualTemperature: number | null
  reconTemperature: number | null
  actualHumidity: number | null
  reconHumidity: number | null
  isAnomaly: boolean
}

export function buildReconstructionSlice(
  telemetry: readonly TelemetryPoint[],
  inference: readonly InferencePoint[],
  limit = 10,
): ReconstructionSlicePoint[] {
  const actualByTs = new Map<string, TelemetryPoint>()
  for (const point of telemetry) {
    actualByTs.set(point.ts, point)
  }
  return inference.slice(-limit).map((point) => {
    const actual = actualByTs.get(point.score_ts)
    return {
      x: historicalDateTimeToDate(point.score_ts),
      ts: point.score_ts,
      actualTemperature: actual?.temperature_c ?? null,
      reconTemperature: point.recon_temperature_c,
      actualHumidity: actual?.relative_humidity_pct ?? null,
      reconHumidity: point.recon_relative_humidity_pct,
      isAnomaly: point.is_anomaly,
    }
  })
}

export interface ReconstructionBand {
  baseline: (number | null)[]
  error: (number | null)[]
}

export function buildReconstructionBand(
  slice: readonly ReconstructionSlicePoint[],
): ReconstructionBand {
  const baseline = slice.map((point) =>
    point.actualTemperature !== null && point.reconTemperature !== null
      ? Math.min(point.actualTemperature, point.reconTemperature)
      : null,
  )
  const error = slice.map((point) =>
    point.actualTemperature !== null && point.reconTemperature !== null
      ? Math.abs(point.actualTemperature - point.reconTemperature)
      : null,
  )
  return { baseline, error }
}

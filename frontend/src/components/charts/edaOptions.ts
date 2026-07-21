import type { CorrelationResponse, HistogramResponse } from '../../contracts/eda'

export interface HistogramChartData {
  labels: string[]
  counts: number[]
}

export interface ScatterChartPoint {
  id: string
  x: number
  y: number
  anomalous: boolean
}

export type ScatterChartData = ScatterChartPoint[]

export function buildHistogramChartData(input: HistogramResponse): HistogramChartData {
  return {
    labels: input.bins.map((bin) => `[${bin.start}, ${bin.end})`),
    counts: input.bins.map((bin) => bin.count),
  }
}

export function buildScatterChartData(input: CorrelationResponse): ScatterChartData {
  return input.points.map((point, index) => ({
    id: `${point.device_id}-${point.ts}-${index}`,
    x: point.x,
    y: point.y,
    anomalous: point.is_candidate_outlier,
  }))
}

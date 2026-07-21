import type {
  ConfusionMatrix,
  PrecisionRecallCurve,
  RocCurve,
} from '../../contracts/modelEvaluation'

export interface ConfusionMatrixChartRow {
  actual: string
  counts: number[]
}

export interface ConfusionMatrixChartData {
  xLabels: string[]
  yLabels: string[]
  rows: ConfusionMatrixChartRow[]
  maxCount: number
}

export interface EvaluationCurvePoint {
  x: number
  y: number
}

export type RocChartData = EvaluationCurvePoint[]
export type PrecisionRecallChartData = EvaluationCurvePoint[]

export function buildConfusionMatrixChartData(input: ConfusionMatrix): ConfusionMatrixChartData {
  return {
    xLabels: [...input.labels],
    yLabels: [...input.labels],
    rows: input.matrix.map((counts, index) => ({
      actual: input.labels[index],
      counts: [...counts],
    })),
    maxCount: input.matrix.reduce((maximum, row) => Math.max(maximum, ...row), 1),
  }
}

export function buildRocChartData(input: RocCurve): RocChartData {
  return input.points.map((point) => ({ x: point.fpr, y: point.tpr }))
}

export function buildPrecisionRecallChartData(
  input: PrecisionRecallCurve,
): PrecisionRecallChartData {
  return input.points.map((point) => ({ x: point.recall, y: point.precision }))
}

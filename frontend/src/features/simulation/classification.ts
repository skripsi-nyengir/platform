import type { InferencePoint } from '../../contracts/inference'
import type { SimInjectionEvent } from '../../contracts/injection'

export type DetectionClassification = 'tp' | 'fn' | 'fp' | 'tn'

export interface ClassifiedDetection {
  point: InferencePoint
  classification: DetectionClassification
}

export interface ClassifiedInjection {
  event: SimInjectionEvent
  classification: 'tp' | 'fn'
}

export interface DetectionClassificationResult {
  detections: ClassifiedDetection[]
  injections: ClassifiedInjection[]
  counts: {
    tp: number
    fn: number
    fp: number
    tn: number
    caughtEvents: number
    totalEvents: number
  }
  metrics: {
    eventHitRate: number
    precision: number
    recall: number
    falsePositiveRate: number
  }
}

function overlaps(
  leftStart: string,
  leftEnd: string,
  rightStart: string,
  rightEnd: string,
): boolean {
  return leftStart <= rightEnd && rightStart <= leftEnd
}

function ratio(numerator: number, denominator: number): number {
  return denominator === 0 ? 0 : numerator / denominator
}

export function classifyDetectionWindows(
  events: readonly SimInjectionEvent[],
  points: readonly InferencePoint[],
): DetectionClassificationResult {
  const truthByPoint = points.map((point) => events.some((event) =>
    overlaps(point.window_start_ts, point.window_end_ts, event.start_ts, event.end_ts),
  ))
  const detections = points.map((point, index): ClassifiedDetection => {
    const injected = truthByPoint[index] ?? false
    return {
      point,
      classification: point.is_anomaly
        ? injected ? 'tp' : 'fp'
        : injected ? 'fn' : 'tn',
    }
  })
  const injections = events.map((event): ClassifiedInjection => ({
    event,
    classification: points.some((point) =>
      point.is_anomaly &&
      overlaps(point.window_start_ts, point.window_end_ts, event.start_ts, event.end_ts),
    ) ? 'tp' : 'fn',
  }))
  const counts = {
    tp: detections.filter((item) => item.classification === 'tp').length,
    fn: detections.filter((item) => item.classification === 'fn').length,
    fp: detections.filter((item) => item.classification === 'fp').length,
    tn: detections.filter((item) => item.classification === 'tn').length,
    caughtEvents: injections.filter((item) => item.classification === 'tp').length,
    totalEvents: injections.length,
  }

  return {
    detections,
    injections,
    counts,
    metrics: {
      eventHitRate: ratio(counts.caughtEvents, counts.totalEvents),
      precision: ratio(counts.tp, counts.tp + counts.fp),
      recall: ratio(counts.tp, counts.tp + counts.fn),
      falsePositiveRate: ratio(counts.fp, counts.fp + counts.tn),
    },
  }
}

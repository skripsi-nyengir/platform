import { historicalDateTimeToDate } from '../../contracts/common'
import type { PostInferenceBin } from '../../contracts/postInferenceBins'

export interface AlertBinInterval {
  start: Date
  end: Date
  isAlert: boolean
}

export interface AlertBinShapes {
  bands: { x: number; width: number }[]
  boundaries: number[]
}

export function toAlertBinIntervals(
  bins: readonly PostInferenceBin[],
): AlertBinInterval[] {
  return bins.map((bin) => ({
    start: historicalDateTimeToDate(bin.start_score_ts),
    end: historicalDateTimeToDate(bin.end_score_ts),
    isAlert: bin.is_alert,
  }))
}

export function buildAlertBinShapes(
  intervals: readonly AlertBinInterval[],
  project: (value: Date) => number,
  bounds: { left: number; right: number },
): AlertBinShapes {
  const clamp = (value: number) =>
    Math.max(bounds.left, Math.min(bounds.right, value))
  const bands: { x: number; width: number }[] = []
  const boundaries: number[] = []
  for (const interval of intervals) {
    const startX = clamp(project(interval.start))
    const endX = clamp(project(interval.end))
    const left = Math.min(startX, endX)
    const right = Math.max(startX, endX)
    if (interval.isAlert && right > left) {
      bands.push({ x: left, width: right - left })
    }
    boundaries.push(left)
  }
  const last = intervals[intervals.length - 1]
  if (last !== undefined) {
    boundaries.push(clamp(project(last.end)))
  }
  return { bands, boundaries }
}

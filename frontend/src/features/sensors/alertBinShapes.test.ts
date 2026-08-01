import { describe, expect, it } from 'vitest'
import type { PostInferenceBin } from '../../contracts/postInferenceBins'
import {
  buildAlertBinShapes,
  toAlertBinIntervals,
  type AlertBinInterval,
} from './alertBinShapes'

const project = (value: Date) => value.getTime() / 1000

function interval(startSec: number, endSec: number, isAlert: boolean): AlertBinInterval {
  return { start: new Date(startSec * 1000), end: new Date(endSec * 1000), isAlert }
}

describe('buildAlertBinShapes', () => {
  it('creates bands only for alert bins and draws every boundary', () => {
    const shapes = buildAlertBinShapes(
      [interval(10, 20, true), interval(20, 30, false), interval(30, 40, true)],
      project,
      { left: 0, right: 100 },
    )
    expect(shapes.bands).toEqual([
      { x: 10, width: 10 },
      { x: 30, width: 10 },
    ])
    expect(shapes.boundaries).toEqual([10, 20, 30, 40])
  })

  it('clamps bands to the drawing bounds', () => {
    const shapes = buildAlertBinShapes([interval(-50, 150, true)], project, {
      left: 0,
      right: 100,
    })
    expect(shapes.bands).toEqual([{ x: 0, width: 100 }])
  })

  it('emits no bands when no bins are alerts', () => {
    const shapes = buildAlertBinShapes([interval(10, 20, false)], project, {
      left: 0,
      right: 100,
    })
    expect(shapes.bands).toEqual([])
    expect(shapes.boundaries).toEqual([10, 20])
  })
})

describe('toAlertBinIntervals', () => {
  it('maps bin timestamps and alert flag to intervals', () => {
    const bin: PostInferenceBin = {
      segment_id: 0,
      bin_ordinal: 0,
      start_score_ts: '2026-05-31T23:47:30',
      end_score_ts: '2026-05-31T23:49:30',
      scored_timestamp_count: 51,
      is_alert: true,
      candidate_alert_count: 3,
      first_alert_ts: '2026-05-31T23:47:30',
      last_alert_ts: '2026-05-31T23:49:30',
      peak_score: 1.4,
      latest_score: 1.1,
      threshold: 1,
      schema_version: 'post-inference-bins-v1',
    }
    const [mapped] = toAlertBinIntervals([bin])
    expect(mapped.isAlert).toBe(true)
    expect(mapped.start).toBeInstanceOf(Date)
    expect(mapped.end.getTime()).toBeGreaterThan(mapped.start.getTime())
  })
})

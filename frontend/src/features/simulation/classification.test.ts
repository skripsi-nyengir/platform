import { describe, expect, it } from 'vitest'
import type { InferencePoint } from '../../contracts/inference'
import type { SimInjectionEvent } from '../../contracts/injection'
import { classifyDetectionWindows } from './classification'

function injection(
  event_id: string,
  start_ts: string,
  end_ts: string,
): SimInjectionEvent {
  return {
    event_id,
    family: 'spike',
    severity: 'high',
    channel: 'suhu',
    channel_index: 0,
    start_ts,
    end_ts,
    start_idx: 0,
    end_idx_exclusive: 1,
    segment_index: 0,
  }
}

function point(
  window_start_ts: string,
  window_end_ts: string,
  is_anomaly: boolean,
): InferencePoint {
  return {
    window_start_ts,
    window_end_ts,
    score_ts: window_end_ts,
    score: is_anomaly ? 2 : 0.5,
    threshold: 1,
    is_anomaly,
    model_version: 'artifact-lstm-ae-v3',
    score_provenance: 'artifact_backed',
  }
}

describe('classifyDetectionWindows', () => {
  it('classifies TP, FN, FP, and TN windows and computes event-level hits', () => {
    const result = classifyDetectionWindows(
      [
        injection('event-1', '2026-04-19T00:00:00', '2026-04-19T00:10:00'),
        injection('event-2', '2026-04-19T00:20:00', '2026-04-19T00:30:00'),
        injection('event-3', '2026-04-19T00:40:00', '2026-04-19T00:50:00'),
      ],
      [
        point('2026-04-19T00:08:00', '2026-04-19T00:12:00', true),
        point('2026-04-19T00:21:00', '2026-04-19T00:22:00', false),
        point('2026-04-19T00:35:00', '2026-04-19T00:41:00', true),
        point('2026-04-19T01:00:00', '2026-04-19T01:05:00', true),
        point('2026-04-19T01:10:00', '2026-04-19T01:15:00', false),
      ],
    )

    expect(result.detections.map((item) => item.classification))
      .toEqual(['tp', 'fn', 'tp', 'fp', 'tn'])
    expect(result.injections.map((item) => item.classification)).toEqual(['tp', 'fn', 'tp'])
    expect(result.counts).toEqual({
      tp: 2,
      fn: 1,
      fp: 1,
      tn: 1,
      caughtEvents: 2,
      totalEvents: 3,
    })
    expect(result.metrics).toEqual({
      eventHitRate: 2 / 3,
      precision: 2 / 3,
      recall: 2 / 3,
      falsePositiveRate: 1 / 2,
    })
  })

  it('counts windows touching an injection boundary as overlapping', () => {
    const result = classifyDetectionWindows(
      [injection('event-1', '2026-04-19T00:10:00', '2026-04-19T00:20:00')],
      [point('2026-04-19T00:00:00', '2026-04-19T00:10:00', true)],
    )

    expect(result.detections[0]?.classification).toBe('tp')
    expect(result.injections[0]?.classification).toBe('tp')
  })
})

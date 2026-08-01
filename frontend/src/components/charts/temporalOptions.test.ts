import { describe, expect, it } from 'vitest'
import type { InferencePoint } from '../../contracts/inference'
import type { TelemetryPoint } from '../../contracts/telemetry'
import { buildReconstructionBand, buildReconstructionSlice } from './temporalOptions'

const t1 = '2026-05-31T23:47:30'
const t2 = '2026-05-31T23:48:00'
const t3 = '2026-05-31T23:48:30'

function telemetry(ts: string, temperature: number | null, humidity: number | null): TelemetryPoint {
  return {
    ts,
    temperature_c: temperature,
    relative_humidity_pct: humidity,
    temperature_c_min: temperature,
    temperature_c_max: temperature,
    relative_humidity_pct_min: humidity,
    relative_humidity_pct_max: humidity,
    sample_count: 1,
    gap_before: false,
  }
}

function inference(
  ts: string,
  recon: { t: number | null; h: number | null },
  isAnomaly = false,
): InferencePoint {
  return {
    window_start_ts: ts,
    window_end_ts: ts,
    score_ts: ts,
    score: 0.5,
    threshold: 1,
    is_anomaly: isAnomaly,
    severity: 'info',
    latest_score: 0.5,
    sample_count: 1,
    model_version: 'test',
    score_provenance: 'artifact_backed',
    recon_temperature_c: recon.t,
    recon_relative_humidity_pct: recon.h,
    band_half_temperature_c: null,
    band_half_relative_humidity_pct: null,
  }
}

describe('buildReconstructionSlice', () => {
  it('aligns actual telemetry to inference by score_ts and passes recon through', () => {
    const slice = buildReconstructionSlice(
      [telemetry(t1, 25, 60), telemetry(t2, 26, 61)],
      [inference(t1, { t: 24.8, h: 59.5 }), inference(t2, { t: 26.1, h: 61.4 }, true)],
    )
    expect(slice).toHaveLength(2)
    expect(slice[0]).toMatchObject({
      ts: t1,
      actualTemperature: 25,
      reconTemperature: 24.8,
      actualHumidity: 60,
      reconHumidity: 59.5,
      isAnomaly: false,
    })
    expect(slice[1].isAnomaly).toBe(true)
  })

  it('yields null actuals when no telemetry matches the score_ts', () => {
    const slice = buildReconstructionSlice([telemetry(t1, 25, 60)], [inference(t3, { t: 24.9, h: 58 })])
    expect(slice[0].actualTemperature).toBeNull()
    expect(slice[0].actualHumidity).toBeNull()
    expect(slice[0].reconTemperature).toBe(24.9)
  })

  it('keeps only the last `limit` inference points', () => {
    const slice = buildReconstructionSlice(
      [],
      [inference(t1, { t: 1, h: 1 }), inference(t2, { t: 2, h: 2 }), inference(t3, { t: 3, h: 3 })],
      2,
    )
    expect(slice.map((point) => point.ts)).toEqual([t2, t3])
  })
})

describe('buildReconstructionBand', () => {
  it('computes baseline=min(actual,recon) and error=|actual-recon| for aligned points', () => {
    const slice = buildReconstructionSlice(
      [telemetry(t1, 25, 60), telemetry(t2, 26, 61)],
      [inference(t1, { t: 24.5, h: 59 }), inference(t2, { t: 26.5, h: 62 })],
    )
    const band = buildReconstructionBand(slice)
    expect(band.baseline).toEqual([24.5, 26])
    expect(band.error).toEqual([0.5, 0.5])
  })

  it('yields null band entries when actual is missing', () => {
    const band = buildReconstructionBand(buildReconstructionSlice([], [inference(t1, { t: 24.9, h: 58 })]))
    expect(band.baseline).toEqual([null])
    expect(band.error).toEqual([null])
  })
})

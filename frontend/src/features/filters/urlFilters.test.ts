import { describe, expect, it } from 'vitest'
import {
  historicalDefaultRange,
  parseEdaUrlState,
  parseUrlFilters,
  telemetryDefaultRange,
  updateEdaUrlState,
  updateUrlFilters,
} from './urlFilters'

describe('B02 URL filters', () => {
  it('uses the B02 source range and rejects legacy sensors', () => {
    expect(parseUrlFilters(new URLSearchParams({ sensor: 'talpha-1' }))).toEqual({
      ...telemetryDefaultRange,
      bucket: '1d',
    })
  })

  it('keeps the 13-month EDA source range separate from telemetry defaults', () => {
    expect(parseEdaUrlState(new URLSearchParams())).toMatchObject(historicalDefaultRange)
  })

  it('round-trips the public sensor and historical model version', () => {
    const next = updateUrlFilters(new URLSearchParams(), {
      sensor: 'b02f3872-ruang-produksi',
      modelVersion: 'preview-usad-v1',
    })
    expect(next.toString()).toContain('sensor=b02f3872-ruang-produksi')
    expect(next.get('model_version')).toBe('preview-usad-v1')
  })

  it('round-trips only the EDA run-selection parameters', () => {
    const next = updateEdaUrlState(new URLSearchParams({ sensor: 'legacy', bucket: '15m' }), {
      mode: 'custom',
      periodKind: 'weekly',
      from: '2026-02-02T00:00:00',
      to: '2026-02-09T00:00:00',
      runId: 'run-weekly',
    })

    expect(parseEdaUrlState(next)).toEqual({
      mode: 'custom',
      periodKind: 'weekly',
      from: '2026-02-02T00:00:00',
      to: '2026-02-09T00:00:00',
      runId: 'run-weekly',
    })
    expect(next.has('sensor')).toBe(false)
    expect(next.has('bucket')).toBe(false)
  })
})

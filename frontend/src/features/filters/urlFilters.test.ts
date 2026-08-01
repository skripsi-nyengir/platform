import { describe, expect, it } from 'vitest'
import {
  historicalDefaultRange,
  parseEdaUrlState,
  parseLiveUrlFilters,
  parseUrlFilters,
  resolveLiveRange,
  telemetryDefaultRange,
  updateEdaUrlState,
  updateLiveUrlFilters,
  updateUrlFilters,
} from './urlFilters'

describe('B02 URL filters', () => {
  it('uses the B02 source range and rejects legacy sensors', () => {
    expect(parseUrlFilters(new URLSearchParams({ sensor: 'talpha-1' }))).toEqual({
      ...telemetryDefaultRange,
      bucket: 'adaptive',
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

  it('defaults live telemetry to a semantic rolling hour', () => {
    expect(parseLiveUrlFilters(new URLSearchParams())).toEqual({ range: '1h' })
    expect(parseLiveUrlFilters(new URLSearchParams({ range: 'invalid' }))).toEqual({ range: '1h' })
  })

  it.each(['1h', '6h', '12h', '24h'] as const)(
    'round-trips the %s rolling range without fixed timestamps',
    (range) => {
      const next = updateLiveUrlFilters(
        new URLSearchParams({ from: '2026-07-01T00:00:00', to: '2026-07-01T01:00:00' }),
        { range },
      )

      expect(next.toString()).toBe(`range=${range}`)
      expect(parseLiveUrlFilters(next)).toEqual({ range })
    },
  )

  it('round-trips custom live bounds for refresh and sharing', () => {
    const next = updateLiveUrlFilters(new URLSearchParams(), {
      range: 'custom',
      from: '2026-07-31T06:00:00',
      to: '2026-07-31T08:00:00',
    })

    expect(next.toString()).toBe(
      'range=custom&from=2026-07-31T06%3A00%3A00&to=2026-07-31T08%3A00%3A00',
    )
    expect(parseLiveUrlFilters(next)).toEqual({
      range: 'custom',
      from: '2026-07-31T06:00:00',
      to: '2026-07-31T08:00:00',
    })
  })

  it('falls back to one hour when custom bounds are incomplete or invalid', () => {
    expect(parseLiveUrlFilters(new URLSearchParams({ range: 'custom' }))).toEqual({ range: '1h' })
    expect(parseLiveUrlFilters(new URLSearchParams({
      range: 'custom',
      from: '2026-07-31T08:00:00',
      to: '2026-07-31T06:00:00',
    }))).toEqual({ range: '1h' })
  })

  it.each([
    ['1h', '2026-07-31T07:00:00', 'raw'],
    ['6h', '2026-07-31T02:00:00', 'one_minute'],
    ['12h', '2026-07-30T20:00:00', 'one_minute'],
    ['24h', '2026-07-30T08:00:00', 'one_minute'],
  ] as const)('resolves %s bounds and buckets at fetch time', (range, from, bucket) => {
    expect(resolveLiveRange({ range }, new Date('2026-07-31T01:00:00Z'))).toEqual({
      from,
      to: '2026-07-31T08:00:00',
      bucket,
    })
  })

  it('uses adaptive bucketing for fixed custom bounds', () => {
    expect(resolveLiveRange({
      range: 'custom',
      from: '2026-07-31T06:00:00',
      to: '2026-07-31T08:00:00',
    }, new Date('2026-08-01T00:00:00Z'))).toEqual({
      from: '2026-07-31T06:00:00',
      to: '2026-07-31T08:00:00',
      bucket: 'adaptive',
    })
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

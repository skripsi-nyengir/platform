import { describe, expect, it } from 'vitest'
import { parseUrlFilters, updateUrlFilters } from './urlFilters'

const defaults = {
  from: '2026-07-18T00:00:00Z',
  to: '2026-07-19T00:00:00Z',
  bucket: '15m',
}

describe('parseUrlFilters', () => {
  it('restores all five URL keys and accepts explicit timezone offsets', () => {
    const params = new URLSearchParams({
      sensor: 'n4',
      from: '2026-07-18T07:00:00+07:00',
      to: '2026-07-19T07:00:00+07:00',
      bucket: '1h',
      model_version: 'model-v2',
    })

    expect(parseUrlFilters(params)).toEqual({
      sensor: 'n4',
      from: '2026-07-18T07:00:00+07:00',
      to: '2026-07-19T07:00:00+07:00',
      bucket: '1h',
      modelVersion: 'model-v2',
    })
  })

  it('normalizes invalid sensor, bucket, and timestamps without timezone to approved defaults', () => {
    const params = new URLSearchParams({
      sensor: 'n7',
      from: '2026-07-18T00:00:00',
      to: '2026-07-19T00:00:00',
      bucket: '2m',
    })

    expect(parseUrlFilters(params)).toEqual(defaults)
  })

  it('normalizes a reversed time range to the complete approved window', () => {
    const params = new URLSearchParams({
      from: '2026-07-20T00:00:00Z',
      to: '2026-07-19T00:00:00Z',
      bucket: '5m',
    })

    expect(parseUrlFilters(params)).toEqual({ ...defaults, bucket: '5m' })
  })

  it('gives a valid route sensor precedence over the query sensor', () => {
    const params = new URLSearchParams({ sensor: 'n2' })

    expect(parseUrlFilters(params, 'n5').sensor).toBe('n5')
    expect(parseUrlFilters(params, 'invalid').sensor).toBe('n2')
  })
})

describe('updateUrlFilters', () => {
  it('preserves unrelated and omitted params while updating supplied required fields', () => {
    const current = new URLSearchParams({
      sensor: 'n1',
      from: defaults.from,
      to: defaults.to,
      bucket: defaults.bucket,
      model_version: 'model-v1',
      tab: 'raw',
    })

    const next = updateUrlFilters(current, {
      from: '2026-07-18T01:00:00Z',
      bucket: '1h',
    })

    expect(next.get('sensor')).toBe('n1')
    expect(next.get('from')).toBe('2026-07-18T01:00:00Z')
    expect(next.get('to')).toBe(defaults.to)
    expect(next.get('bucket')).toBe('1h')
    expect(next.get('model_version')).toBe('model-v1')
    expect(next.get('tab')).toBe('raw')
    expect(current.get('from')).toBe(defaults.from)
  })

  it('deletes explicitly cleared optional filters without serializing undefined', () => {
    const current = new URLSearchParams({
      sensor: 'n1',
      model_version: 'model-v1',
      tab: 'summary',
    })

    const next = updateUrlFilters(current, { sensor: undefined, modelVersion: '' })

    expect(next.has('sensor')).toBe(false)
    expect(next.has('model_version')).toBe(false)
    expect(next.get('tab')).toBe('summary')
    expect(next.toString()).not.toContain('undefined')
  })

  it('deletes explicitly empty required string fields for reload normalization', () => {
    const current = new URLSearchParams({
      from: defaults.from,
      to: defaults.to,
      bucket: defaults.bucket,
    })

    const next = updateUrlFilters(current, { from: '', to: '' })

    expect(next.has('from')).toBe(false)
    expect(next.has('to')).toBe(false)
    expect(next.get('bucket')).toBe(defaults.bucket)
  })
})

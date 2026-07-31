import { describe, expect, it } from 'vitest'
import { formatWibDateTime } from './dateTime'

describe('formatWibDateTime', () => {
  it('formats naive WIB parts without shifting the time', () => {
    expect(formatWibDateTime('2026-07-31T00:05:09')).toBe('31 Jul 2026, 00:05:09')
  })
})

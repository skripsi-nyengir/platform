import { describe, expect, it } from 'vitest'
import { SensorIdSchema } from './common'

describe('B02 public contracts', () => {
  it('accepts only the public B02 device', () => {
    expect(SensorIdSchema.parse('b02f3872-ruang-produksi')).toBe('b02f3872-ruang-produksi')
    expect(SensorIdSchema.safeParse('talpha-1').success).toBe(false)
  })

})

import { describe, expect, it } from 'vitest'
import { previewDevice } from '../../mocks/fixtures/preview'

describe('telemetry identity', () => {
  it('uses the single B02 device and WIB timezone', () => {
    expect(previewDevice).toMatchObject({
      device_id: 'b02f3872-ruang-produksi',
      time_zone: 'Asia/Jakarta',
    })
  })
})

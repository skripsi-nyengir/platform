import { describe, expect, it } from 'vitest'
import { buildTemporalChartData } from './temporalOptions'
import { theme } from '../../theme/theme'

describe('temporal chart data', () => {
  it('keeps B02 historical timestamps and one score series aligned', () => {
    const result = buildTemporalChartData({
      theme,
      sensorId: 'b02f3872-ruang-produksi',
      from: '2026-02-01T00:00:00',
      to: '2026-03-01T00:00:00',
      telemetry: [],
      inference: [],
      alerts: [],
    })
    expect(result.scores).toEqual([])
  })
})

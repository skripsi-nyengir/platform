import { describe, expect, it } from 'vitest'
import { ReplayJobRequestSchema } from './contracts/preview'
import {
  publicDeviceId,
  sensorIds,
  sensorLabels,
  wibHistoricalDateTimeToUtcInstant,
} from './contracts/common'
import { AlertEventsQuerySchema } from './contracts/alerts'
import { previewDevice } from './mocks/fixtures/preview'

describe('B02F3872 preview contract', () => {
  it('exposes one WIB telemetry device', () => {
    expect(sensorIds).toEqual([publicDeviceId])
    expect(sensorLabels[publicDeviceId]).toBe('B02')
    expect(previewDevice).toMatchObject({
      time_zone: 'Asia/Jakarta',
      channels: ['suhu', 'rh'],
      import_readiness: 'ready',
    })
  })

  it('enforces half-open replay ordering and the 31-day maximum', () => {
    const base = {
      command_id: '550e8400-e29b-41d4-a716-446655440000',
      device_id: publicDeviceId,
      from: '2026-02-01T00:00:00',
    } as const
    expect(ReplayJobRequestSchema.safeParse({ ...base, to: '2026-03-04T00:00:00' }).success)
      .toBe(true)
    expect(ReplayJobRequestSchema.safeParse({ ...base, to: '2026-03-04T00:00:01' }).success)
      .toBe(false)
    expect(ReplayJobRequestSchema.safeParse({ ...base, to: base.from }).success).toBe(false)
  })

  it('converts WIB corpus filters to UTC operational instants for alert event queries', () => {
    const from = wibHistoricalDateTimeToUtcInstant('2026-02-01T00:00:00')
    const to = wibHistoricalDateTimeToUtcInstant('2026-02-02T00:00:00')
    expect({ from, to }).toEqual({
      from: '2026-01-31T17:00:00.000Z',
      to: '2026-02-01T17:00:00.000Z',
    })
    expect(AlertEventsQuerySchema.safeParse({ from, to }).success).toBe(true)
    expect(AlertEventsQuerySchema.safeParse({
      from: '2026-02-01T00:00:00',
      to: '2026-02-02T00:00:00',
    }).success).toBe(false)
  })
})

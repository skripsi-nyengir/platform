import { afterEach, describe, expect, it, vi } from 'vitest'
import { getAlertEvents } from './alerts'
import { computeEda, getEdaPeriods } from './eda'
import { edaCacheHitResponse } from '../mocks/fixtures/eda'

afterEach(() => vi.unstubAllGlobals())

describe('B02 API adapters', () => {
  it('queries selected alert lifecycle by alert id without corpus bounds', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(new Response(JSON.stringify({
      request_id: 'req-events',
      time_zone: 'Asia/Jakarta',
      events: [],
      next_cursor: null,
      returned_count: 0,
    }), { headers: { 'content-type': 'application/json' } })))
    vi.stubGlobal('fetch', fetchMock)
    await getAlertEvents({ alertId: 'alert-b02', limit: 200 })
    expect(fetchMock).toHaveBeenCalledWith('/api/alert-events?alert_id=alert-b02&limit=200', expect.anything())
  })

  it.each(['daily', 'weekly', 'monthly'] as const)(
    'serializes the %s period kind exactly',
    async (periodKind) => {
      const fetchMock = vi.fn(() => Promise.resolve(new Response(JSON.stringify({
        request_id: 'req-eda-periods',
        period_kind: periodKind,
        items: [],
        next_cursor: null,
        returned_count: 0,
      }), { headers: { 'content-type': 'application/json' } })))
      vi.stubGlobal('fetch', fetchMock)

      await getEdaPeriods({ period_kind: periodKind, limit: 20 })

      expect(fetchMock).toHaveBeenCalledWith(
        `/api/eda/periods?period_kind=${periodKind}&limit=20`,
        expect.anything(),
      )
    },
  )

  it('preserves the exact custom half-open range in the compute body', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(new Response(
      JSON.stringify(edaCacheHitResponse),
      { headers: { 'content-type': 'application/json' } },
    )))
    vi.stubGlobal('fetch', fetchMock)

    await computeEda({
      device_id: 'b02f3872-39a2-4b6f-a4ec-045a287fde4b',
      time_zone: 'Asia/Jakarta',
      period_kind: 'custom',
      from: '2026-02-01T00:00:00',
      to: '2026-02-02T00:00:00',
    })

    expect(fetchMock).toHaveBeenCalledWith('/api/eda/compute', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({
        device_id: 'b02f3872-39a2-4b6f-a4ec-045a287fde4b',
        time_zone: 'Asia/Jakarta',
        period_kind: 'custom',
        from: '2026-02-01T00:00:00',
        to: '2026-02-02T00:00:00',
      }),
    }))
  })
})

import { renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createQueryTestHarness } from '../test/queryTestUtils'
import { useLiveTelemetryData } from './useLiveTelemetryData'

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('live telemetry queries', () => {
  it('polls telemetry, inference, alerts, and health every 3000ms with semantic keys', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.setSystemTime(new Date('2026-07-31T01:00:00Z'))
    const harness = createQueryTestHarness()
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    const view = renderHook(
      () => useLiveTelemetryData('b02f3872-ruang-produksi', { range: '1h' }),
      { wrapper: harness.wrapper },
    )

    try {
      await vi.waitFor(() => expect(fetchSpy.mock.calls.length).toBeGreaterThanOrEqual(6))
      const liveQueries = harness.queryClient.getQueryCache().getAll()
        .filter((query) => query.queryKey[0] === 'live')
      expect(liveQueries).toHaveLength(7)
      expect(liveQueries.map((query) => query.queryKey)).toContainEqual([
        'live',
        'telemetry-history',
        'b02f3872-ruang-produksi',
        '1h',
        null,
        null,
      ])
      expect(liveQueries.flatMap((query) => query.queryKey)).not.toContain('2026-07-31T08:00:00')

      const initialKeys = liveQueries.map((query) => query.queryHash).toSorted()
      await vi.advanceTimersByTimeAsync(3_000)
      await vi.waitFor(() => expect(fetchSpy.mock.calls.length).toBeGreaterThanOrEqual(12))

      const requestUrls = fetchSpy.mock.calls.map(([input]) => String(input))
      const telemetryUrls = requestUrls.filter((url) => url.includes('/api/telemetry/history'))
      const inferenceUrls = requestUrls.filter((url) => url.includes('/api/inference-results'))
      expect(telemetryUrls.some((url) => url.includes('to=2026-07-31T08%3A00%3A00'))).toBe(true)
      expect(telemetryUrls.some((url) => url.includes('to=2026-07-31T08%3A00%3A03'))).toBe(true)
      expect(inferenceUrls.some((url) => url.includes('to=2026-07-31T08%3A00%3A00'))).toBe(true)
      expect(inferenceUrls.some((url) => url.includes('to=2026-07-31T08%3A00%3A03'))).toBe(true)
      expect(harness.queryClient.getQueryCache().getAll()
        .filter((query) => query.queryKey[0] === 'live')
        .map((query) => query.queryHash)
        .toSorted()).toEqual(initialKeys)
      expect(view.result.current.telemetryHistory).toBeDefined()
    } finally {
      view.unmount()
      fetchSpy.mockRestore()
      harness.restore()
    }
  })
})

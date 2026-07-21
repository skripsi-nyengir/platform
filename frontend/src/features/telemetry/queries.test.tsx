import { act, renderHook, waitFor } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { server } from '../../mocks/node'
import {
  createQueryTestHarness,
  type QueryTestHarness,
} from '../../test/queryTestUtils'
import { useLatestTelemetryQuery, useTelemetryHistoryQuery } from './queries'

const from = '2026-07-19T10:00:00Z'
const to = '2026-07-19T10:30:00Z'

let harness: QueryTestHarness

beforeEach(() => {
  harness = createQueryTestHarness()
})

afterEach(() => {
  harness.restore()
})

describe('telemetry queries', () => {
  it('uses normalized primitive keys and polls only latest telemetry every 10 seconds', async () => {
    const latest = renderHook(() => useLatestTelemetryQuery('n2'), { wrapper: harness.wrapper })
    const history = renderHook(
      () => useTelemetryHistoryQuery({ deviceId: 'n2', from, to }),
      { wrapper: harness.wrapper },
    )

    await waitFor(() => expect(latest.result.current.isSuccess).toBe(true))
    await waitFor(() => expect(history.result.current.isSuccess).toBe(true))

    const latestKey = ['telemetry', 'latest', 'n2'] as const
    const historyKey = ['telemetry', 'history', 'n2', from, to, 'raw', 500, null] as const
    const latestQuery = harness.queryClient.getQueryCache().find({ queryKey: latestKey })
    const historyQuery = harness.queryClient.getQueryCache().find({ queryKey: historyKey })

    expect(latestQuery?.queryKey).toEqual(latestKey)
    expect(latestQuery?.options).toHaveProperty('refetchInterval', 10_000)
    expect(historyQuery?.queryKey).toEqual(historyKey)
    expect(historyQuery?.options).not.toHaveProperty('refetchInterval')
    expect([...latestKey, ...historyKey].every((value) =>
      value === null || typeof value === 'string' || typeof value === 'number',
    )).toBe(true)
  })

  it('forwards and consumes the query cancellation signal', async () => {
    let observedSignal: AbortSignal | undefined
    globalThis.fetch = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      observedSignal = init?.signal ?? undefined
      return new Promise<Response>((_resolve, reject) => {
        observedSignal?.addEventListener('abort', () => reject(observedSignal?.reason), { once: true })
      })
    })
    const query = renderHook(() => useLatestTelemetryQuery('n1'), { wrapper: harness.wrapper })

    await waitFor(() => expect(observedSignal).toBeDefined())
    query.unmount()

    await waitFor(() => expect(observedSignal?.aborted).toBe(true))
  })

  it('retains successful latest data and reports a background refetch error', async () => {
    const query = renderHook(() => useLatestTelemetryQuery(), { wrapper: harness.wrapper })
    await waitFor(() => expect(query.result.current.isSuccess).toBe(true))
    const confirmedData = query.result.current.data

    server.use(
      http.get(`${window.location.origin}/api/telemetry/latest`, () =>
        HttpResponse.json({ message: 'background failure' }, { status: 503 }),
      ),
    )
    await act(async () => {
      await query.result.current.refetch()
    })

    await waitFor(() => expect(query.result.current.isRefetchError).toBe(true))
    expect(query.result.current.data).toBe(confirmedData)
  })
})

import { act, renderHook, waitFor } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { server } from '../../mocks/node'
import {
  createQueryTestHarness,
  type QueryTestHarness,
} from '../../test/queryTestUtils'
import { useSystemStatusQuery } from './query'

let harness: QueryTestHarness

beforeEach(() => {
  harness = createQueryTestHarness()
})

afterEach(() => {
  harness.restore()
  vi.restoreAllMocks()
})

describe('useSystemStatusQuery', () => {
  it('uses the stable primitive key and polls every 30 seconds', async () => {
    const query = renderHook(() => useSystemStatusQuery(), { wrapper: harness.wrapper })
    await waitFor(() => expect(query.result.current.isSuccess).toBe(true))

    const key = ['system', 'status'] as const
    const cached = harness.queryClient.getQueryCache().find({ queryKey: key })
    expect(cached?.queryKey).toEqual(key)
    expect(cached?.options).toHaveProperty('refetchInterval', 30_000)
    expect(cached?.options).toHaveProperty('staleTime', 30_000)
  })

  it('retains the last successful snapshot timestamp when a background refetch fails', async () => {
    const now = vi.spyOn(Date, 'now').mockReturnValue(Date.parse('2026-07-19T10:30:05Z'))
    const query = renderHook(() => useSystemStatusQuery(), { wrapper: harness.wrapper })
    await waitFor(() => expect(query.result.current.isSuccess).toBe(true))
    const confirmedData = query.result.current.data
    const confirmedAt = query.result.current.dataUpdatedAt

    server.use(
      http.get(`${window.location.origin}/api/system/status`, () =>
        HttpResponse.json({ message: 'background failure' }, { status: 503 }),
      ),
    )
    now.mockReturnValue(Date.parse('2026-07-19T10:31:10Z'))
    await act(async () => {
      await query.result.current.refetch()
    })

    await waitFor(() => expect(query.result.current.isRefetchError).toBe(true))
    expect(query.result.current.data).toBe(confirmedData)
    expect(query.result.current.dataUpdatedAt).toBe(confirmedAt)
  })
})

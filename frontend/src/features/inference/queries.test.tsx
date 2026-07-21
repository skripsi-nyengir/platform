import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import {
  createQueryTestHarness,
  type QueryTestHarness,
} from '../../test/queryTestUtils'
import { useInferenceResultsQuery } from './queries'

const from = '2026-07-19T10:00:00Z'
const to = '2026-07-19T10:30:00Z'

let harness: QueryTestHarness

beforeEach(() => {
  harness = createQueryTestHarness()
})

afterEach(() => {
  harness.restore()
})

describe('useInferenceResultsQuery', () => {
  it('normalizes schema defaults into a primitive key and does not poll', async () => {
    const query = renderHook(
      () => useInferenceResultsQuery({ deviceId: 'n4', from, to, modelVersion: 'model-v2' }),
      { wrapper: harness.wrapper },
    )
    await waitFor(() => expect(query.result.current.isSuccess).toBe(true))

    const key = [
      'inference',
      'results',
      'n4',
      from,
      to,
      'raw',
      500,
      null,
      'model-v2',
    ] as const
    const cached = harness.queryClient.getQueryCache().find({ queryKey: key })

    expect(cached?.queryKey).toEqual(key)
    expect(cached?.options).not.toHaveProperty('refetchInterval')
    expect(key.every((value) =>
      value === null || typeof value === 'string' || typeof value === 'number',
    )).toBe(true)
  })
})

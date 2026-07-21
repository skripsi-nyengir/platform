import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { modelEvaluationSummaries } from '../../mocks/fixtures/modelEvaluations'
import {
  createQueryTestHarness,
  type QueryTestHarness,
} from '../../test/queryTestUtils'
import {
  normalizeModelEvaluationVersion,
  useModelEvaluationQuery,
  useModelEvaluationsQuery,
} from './queries'

let harness: QueryTestHarness

beforeEach(() => {
  harness = createQueryTestHarness()
})

afterEach(() => {
  harness.restore()
})

describe('model evaluation queries', () => {
  it('restores available versions and normalizes missing or invalid selections', () => {
    expect(normalizeModelEvaluationVersion(modelEvaluationSummaries, 'model-v1')).toBe('model-v1')
    expect(normalizeModelEvaluationVersion(modelEvaluationSummaries, 'missing')).toBe('model-v2')
    expect(normalizeModelEvaluationVersion(modelEvaluationSummaries)).toBe('model-v2')
    expect(normalizeModelEvaluationVersion([], 'model-v1')).toBeUndefined()
  })

  it('normalizes list defaults into a primitive non-polling key', async () => {
    const query = renderHook(() => useModelEvaluationsQuery(), { wrapper: harness.wrapper })
    await waitFor(() => expect(query.result.current.isSuccess).toBe(true))

    const key = ['model-evaluations', 'list', 1, 25] as const
    const cached = harness.queryClient.getQueryCache().find({ queryKey: key })
    expect(cached?.queryKey).toEqual(key)
    expect(cached?.options).not.toHaveProperty('refetchInterval')
  })

  it('keeps undefined detail disabled and fetches each selected version once without polling', async () => {
    const relativeFetch = globalThis.fetch
    const fetchSpy = vi.fn(relativeFetch)
    globalThis.fetch = fetchSpy
    const query = renderHook(({ version }) => useModelEvaluationQuery(version), {
      initialProps: { version: undefined as string | undefined },
      wrapper: harness.wrapper,
    })

    const disabledKey = ['model-evaluations', 'detail', null] as const
    const disabled = harness.queryClient.getQueryCache().find({ queryKey: disabledKey })
    expect(disabled?.queryKey).toEqual(disabledKey)
    expect(disabled?.state.fetchStatus).toBe('idle')
    expect(fetchSpy).not.toHaveBeenCalled()

    query.rerender({ version: 'model-v1' })
    await waitFor(() => expect(query.result.current.isSuccess).toBe(true))
    expect(fetchSpy).toHaveBeenCalledOnce()
    const firstVersion = harness.queryClient.getQueryCache().find({
      queryKey: ['model-evaluations', 'detail', 'model-v1'],
    })
    expect(firstVersion?.options).not.toHaveProperty('refetchInterval')

    query.rerender({ version: 'model-v2' })
    await waitFor(() => expect(query.result.current.data?.version).toBe('model-v2'))
    expect(fetchSpy).toHaveBeenCalledTimes(2)
    const secondVersion = harness.queryClient.getQueryCache().find({
      queryKey: ['model-evaluations', 'detail', 'model-v2'],
    })
    expect(secondVersion?.options).not.toHaveProperty('refetchInterval')
  })
})

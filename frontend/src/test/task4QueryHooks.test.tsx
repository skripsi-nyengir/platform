import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, expectTypeOf, it, vi } from 'vitest'
import { ApiError } from '../api/errors'
import type { AlertMutationResponse } from '../contracts/alerts'
import type { LatestTelemetryResponse } from '../contracts/telemetry'
import { useAlertEventsQuery, useCurrentAlertsQuery } from '../features/alerts/queries'
import { useAlertLifecycleMutation } from '../features/alerts/useAlertLifecycleMutation'
import {
  useEdaCorrelationQuery,
  useEdaDistributionsQuery,
  useEdaSummaryQuery,
} from '../features/eda/queries'
import { useInferenceResultsQuery } from '../features/inference/queries'
import {
  useModelEvaluationQuery,
  useModelEvaluationsQuery,
} from '../features/modelEvaluation/queries'
import { useSystemStatusQuery } from '../features/systemHealth/query'
import {
  useLatestTelemetryQuery,
  useTelemetryHistoryQuery,
} from '../features/telemetry/queries'
import { createQueryTestHarness, type QueryTestHarness } from './queryTestUtils'

const from = '2026-07-19T10:00:00Z'
const to = '2026-07-19T10:30:00Z'

let harness: QueryTestHarness

beforeEach(() => {
  harness = createQueryTestHarness()
})

afterEach(() => {
  harness.restore()
  vi.restoreAllMocks()
})

describe('Task 4 query hooks', () => {
  it('exposes the registered API error and downstream data types', () => {
    const query = renderHook(() => useLatestTelemetryQuery(), { wrapper: harness.wrapper })
    const mutation = renderHook(() => useAlertLifecycleMutation(), { wrapper: harness.wrapper })

    expectTypeOf(query.result.current.error).toEqualTypeOf<ApiError | null>()
    expectTypeOf(mutation.result.current.error).toEqualTypeOf<ApiError | null>()
    expectTypeOf(query.result.current.data).toEqualTypeOf<LatestTelemetryResponse | undefined>()
    expectTypeOf(mutation.result.current.data).toEqualTypeOf<AlertMutationResponse | undefined>()
  })

  it('shares cache entries for omitted and explicit schema defaults', async () => {
    renderHook(() => useTelemetryHistoryQuery({ deviceId: 'n2', from, to }), {
      wrapper: harness.wrapper,
    })
    renderHook(
      () => useTelemetryHistoryQuery({ deviceId: 'n2', from, to, bucket: 'raw', limit: 500 }),
      { wrapper: harness.wrapper },
    )
    renderHook(() => useInferenceResultsQuery({ deviceId: 'n4', from, to }), {
      wrapper: harness.wrapper,
    })
    renderHook(
      () => useInferenceResultsQuery({ deviceId: 'n4', from, to, bucket: 'raw', limit: 500 }),
      { wrapper: harness.wrapper },
    )
    renderHook(() => useCurrentAlertsQuery(), { wrapper: harness.wrapper })
    renderHook(() => useCurrentAlertsQuery({ page: 1, pageSize: 25 }), {
      wrapper: harness.wrapper,
    })
    renderHook(() => useAlertEventsQuery(), { wrapper: harness.wrapper })
    renderHook(() => useAlertEventsQuery({ limit: 200 }), { wrapper: harness.wrapper })
    renderHook(() => useEdaDistributionsQuery({ from, to, field: 'score' }), {
      wrapper: harness.wrapper,
    })
    renderHook(() => useEdaDistributionsQuery({ from, to, field: 'score', bins: 20 }), {
      wrapper: harness.wrapper,
    })
    renderHook(() => useEdaCorrelationQuery({ from, to }), { wrapper: harness.wrapper })
    renderHook(
      () => useEdaCorrelationQuery({
        from,
        to,
        xField: 'temperature_c',
        yField: 'relative_humidity_pct',
        maxPoints: 1_000,
      }),
      { wrapper: harness.wrapper },
    )
    renderHook(() => useModelEvaluationsQuery(), { wrapper: harness.wrapper })
    renderHook(() => useModelEvaluationsQuery({ page: 1, pageSize: 25 }), {
      wrapper: harness.wrapper,
    })

    await waitFor(() => expect(harness.queryClient.isFetching()).toBe(0))

    const keys = [
      ['telemetry', 'history', 'n2', from, to, 'raw', 500, null],
      ['inference', 'results', 'n4', from, to, 'raw', 500, null, null],
      ['alerts', 'current', null, null, 1, 25],
      ['alerts', 'events', null, null, null, null, 200, null],
      ['eda', 'distributions', null, from, to, 'score', 20],
      [
        'eda',
        'correlation',
        null,
        from,
        to,
        'temperature_c',
        'relative_humidity_pct',
        1_000,
        null,
      ],
      ['model-evaluations', 'list', 1, 25],
    ]

    for (const queryKey of keys) {
      expect(harness.queryClient.getQueryCache().findAll({ queryKey, exact: true })).toHaveLength(1)
      expect(queryKey.every((value) =>
        value === null || typeof value === 'string' || typeof value === 'number',
      )).toBe(true)
    }
  })

  it('forwards a consumed cancellation signal through every query function', async () => {
    const observedSignals: AbortSignal[] = []
    globalThis.fetch = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      const signal = init?.signal
      if (!(signal instanceof AbortSignal)) throw new Error('Expected a request AbortSignal')
      observedSignals.push(signal)
      return new Promise<Response>((_resolve, reject) => {
        signal.addEventListener('abort', () => reject(signal.reason), { once: true })
      })
    })

    const queries = renderHook(() => {
      useLatestTelemetryQuery('n1')
      useTelemetryHistoryQuery({ deviceId: 'n2', from, to })
      useInferenceResultsQuery({ deviceId: 'n3', from, to })
      useCurrentAlertsQuery()
      useAlertEventsQuery()
      useEdaSummaryQuery({ sensor: 'n4', from, to, bucket: '15m' })
      useEdaDistributionsQuery({ from, to, field: 'score' })
      useEdaCorrelationQuery({ from, to })
      useModelEvaluationsQuery()
      useModelEvaluationQuery('model-v1')
      useSystemStatusQuery()
    }, { wrapper: harness.wrapper })

    await waitFor(() => expect(observedSignals).toHaveLength(11))
    queries.unmount()
    await waitFor(() => expect(observedSignals.every((signal) => signal.aborted)).toBe(true))
  })

  it('keeps missing and empty model versions disabled at the same normalized key', () => {
    const missing = renderHook(() => useModelEvaluationQuery(), { wrapper: harness.wrapper })
    const empty = renderHook(() => useModelEvaluationQuery(''), { wrapper: harness.wrapper })
    const key = ['model-evaluations', 'detail', null]

    expect(missing.result.current.fetchStatus).toBe('idle')
    expect(empty.result.current.fetchStatus).toBe('idle')
    expect(harness.queryClient.getQueryCache().findAll({ queryKey: key, exact: true })).toHaveLength(1)
  })
})

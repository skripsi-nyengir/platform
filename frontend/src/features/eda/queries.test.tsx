import { renderHook, waitFor } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { server } from '../../mocks/node'
import {
  createQueryTestHarness,
  type QueryTestHarness,
} from '../../test/queryTestUtils'
import {
  useEdaCorrelationQuery,
  useEdaDistributionsQuery,
  useEdaSummaryQuery,
} from './queries'

const from = '2026-07-19T10:00:00Z'
const to = '2026-07-19T10:30:00Z'
const origin = window.location.origin

let harness: QueryTestHarness

beforeEach(() => {
  harness = createQueryTestHarness()
})

afterEach(() => {
  harness.restore()
})

describe('EDA queries', () => {
  it('maps URL sensor to summary deviceId, ignores modelVersion, and does not poll', async () => {
    const query = renderHook(
      () => useEdaSummaryQuery({ sensor: 'n2', from, to, bucket: '15m', modelVersion: 'ignored' }),
      { wrapper: harness.wrapper },
    )
    await waitFor(() => expect(query.result.current.isSuccess).toBe(true))

    const key = ['eda', 'summary', 'n2', from, to, '15m'] as const
    const cached = harness.queryClient.getQueryCache().find({ queryKey: key })
    expect(cached?.queryKey).toEqual(key)
    expect(cached?.options).not.toHaveProperty('refetchInterval')
    expect(cached?.queryKey).not.toContain('ignored')
  })

  it('normalizes distribution and correlation defaults into primitive non-polling keys', async () => {
    const distribution = renderHook(
      () => useEdaDistributionsQuery({ from, to, field: 'score' }),
      { wrapper: harness.wrapper },
    )
    const correlation = renderHook(
      () => useEdaCorrelationQuery({ from, to }),
      { wrapper: harness.wrapper },
    )

    await waitFor(() => expect(distribution.result.current.isSuccess).toBe(true))
    await waitFor(() => expect(correlation.result.current.isSuccess).toBe(true))

    const distributionKey = ['eda', 'distributions', null, from, to, 'score', 20] as const
    const correlationKey = [
      'eda',
      'correlation',
      null,
      from,
      to,
      'temperature_c',
      'relative_humidity_pct',
      1_000,
      null,
    ] as const
    const distributionQuery = harness.queryClient.getQueryCache().find({ queryKey: distributionKey })
    const correlationQuery = harness.queryClient.getQueryCache().find({ queryKey: correlationKey })

    expect(distributionQuery?.options).not.toHaveProperty('refetchInterval')
    expect(correlationQuery?.options).not.toHaveProperty('refetchInterval')
    expect([...distributionKey, ...correlationKey].every((value) =>
      value === null || typeof value === 'string' || typeof value === 'number',
    )).toBe(true)
  })

  it('keeps a failed correlation request independent from a successful distribution request', async () => {
    server.use(
      http.get(`${origin}/api/eda/correlation`, () =>
        HttpResponse.json(
          {
            type: 'https://example.invalid/problems/eda-correlation',
            title: 'Correlation unavailable',
            status: 503,
            detail: 'Correlation failed independently',
            instance: '/api/eda/correlation',
            request_id: 'req_eda_correlation_failed',
          },
          { status: 503 },
        ),
      ),
    )
    const distribution = renderHook(
      () => useEdaDistributionsQuery({ from, to, field: 'temperature_c', bins: 10 }),
      { wrapper: harness.wrapper },
    )
    const correlation = renderHook(
      () => useEdaCorrelationQuery({ from, to, maxPoints: 100 }),
      { wrapper: harness.wrapper },
    )

    await waitFor(() => expect(distribution.result.current.isSuccess).toBe(true))
    await waitFor(() => expect(correlation.result.current.isError).toBe(true))

    expect(distribution.result.current.data?.sample_count).toBe(36)
    expect(correlation.result.current.error).toMatchObject({
      requestId: 'req_eda_correlation_failed',
    })
  })
})

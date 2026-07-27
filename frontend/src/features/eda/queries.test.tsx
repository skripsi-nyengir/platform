import { renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it } from 'vitest'
import { edaPublishedCustomRun, edaReadyMonthlyRun, edaRunningCustomJob } from '../../mocks/fixtures/eda'
import { server } from '../../mocks/node'
import { createQueryTestHarness, type QueryTestHarness } from '../../test/queryTestUtils'
import {
  edaQueryKeys,
  useEdaJobQuery,
  useEdaPeriodsQuery,
  useEdaSectionQuery,
} from './queries'

const harnesses: QueryTestHarness[] = []

function harness(): QueryTestHarness {
  const value = createQueryTestHarness()
  harnesses.push(value)
  return value
}

afterEach(() => {
  for (const value of harnesses.splice(0)) value.restore()
})

describe('EDA queries', () => {
  it('uses stable period and section query keys', async () => {
    const testHarness = harness()
    const periods = renderHook(
      () => useEdaPeriodsQuery({ period_kind: 'monthly' }),
      { wrapper: testHarness.wrapper },
    )

    await waitFor(() => expect(periods.result.current.data?.items[0]?.run_id)
      .toBe(edaReadyMonthlyRun.run_id))
    expect(edaQueryKeys.periods({ period_kind: 'monthly', limit: 25, cursor: null }))
      .toEqual(['eda', 'periods', 'monthly', 25, null])
    expect(edaQueryKeys.section(edaReadyMonthlyRun.run_id, 'quality_overview'))
      .toEqual(['eda', 'run', edaReadyMonthlyRun.run_id, 'section', 'quality_overview'])
  })

  it('polls active jobs every second and stops after success', async () => {
    let requests = 0
    const succeededJob = {
      ...edaRunningCustomJob,
      status: 'succeeded' as const,
      terminal: true,
      completed_at: '2026-07-26T07:04:00Z',
      run_id: edaPublishedCustomRun.run_id,
    }
    server.use(http.get('/api/eda/jobs/:jobId', () => {
      requests += 1
      return HttpResponse.json({
        request_id: `req-job-${requests}`,
        job: requests === 1 ? edaRunningCustomJob : succeededJob,
      })
    }))
    const testHarness = harness()
    const { result } = renderHook(
      () => useEdaJobQuery(edaRunningCustomJob.job_id),
      { wrapper: testHarness.wrapper },
    )

    await waitFor(() => expect(result.current.data?.job.status).toBe('succeeded'), {
      timeout: 2_500,
    })
    expect(requests).toBe(2)
    await new Promise((resolve) => globalThis.setTimeout(resolve, 1_100))
    expect(requests).toBe(2)
  })

  it('aborts an in-flight job request when the last observer unmounts', async () => {
    let requestStarted = false
    let requestAborted = false
    server.use(http.get('/api/eda/jobs/:jobId', async ({ request }) => {
      requestStarted = true
      await new Promise<void>((resolve) => {
        request.signal.addEventListener('abort', () => {
          requestAborted = true
          resolve()
        }, { once: true })
      })
      return HttpResponse.json({ request_id: 'req-aborted', job: edaRunningCustomJob })
    }))
    const testHarness = harness()
    const { unmount } = renderHook(
      () => useEdaJobQuery(edaRunningCustomJob.job_id),
      { wrapper: testHarness.wrapper },
    )

    await waitFor(() => expect(requestStarted).toBe(true))
    unmount()
    await waitFor(() => expect(requestAborted).toBe(true))
  })

  it('keeps section requests isolated when one endpoint fails', async () => {
    server.use(http.get('/api/eda/runs/:runId/sections/relationships', ({ request }) => (
      HttpResponse.json({
        type: 'about:blank',
        title: 'EDA section failed',
        status: 500,
        detail: 'Bagian hubungan tidak dapat dimuat.',
        instance: new URL(request.url).pathname,
        request_id: 'req-section-failed',
      }, { status: 500 })
    )))
    const testHarness = harness()
    const { result } = renderHook(() => ({
      quality: useEdaSectionQuery(edaReadyMonthlyRun.run_id, 'quality_overview'),
      relationships: useEdaSectionQuery(edaReadyMonthlyRun.run_id, 'relationships'),
    }), { wrapper: testHarness.wrapper })

    await waitFor(() => expect(result.current.quality.data?.status).toBe('complete'))
    await waitFor(() => expect(result.current.relationships.isError).toBe(true))
    expect(result.current.quality.isError).toBe(false)
    expect(result.current.relationships.error?.message).toBe('Bagian hubungan tidak dapat dimuat.')
  })
})

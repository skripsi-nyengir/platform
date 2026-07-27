import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import type { PropsWithChildren } from 'react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { EdaRunSummary } from '../../contracts/eda'
import {
  edaCacheHitResponse,
  edaFailedJob,
  edaPublishedCustomRun,
  edaReadyMonthlyRun,
  edaRunningComputeResponse,
  edaRunningCustomJob,
} from '../../mocks/fixtures/eda'
import { server } from '../../mocks/node'
import { createQueryTestHarness, type QueryTestHarness } from '../../test/queryTestUtils'
import { EdaRunControls } from './EdaRunControls'

const harnesses: QueryTestHarness[] = []

function LocationProbe() {
  return <output data-testid="location-search">{useLocation().search}</output>
}

function renderControls(initialEntry = '/', onRunSelected = vi.fn()) {
  const harness = createQueryTestHarness()
  harnesses.push(harness)
  const QueryProvider = harness.wrapper

  function Wrapper({ children }: PropsWithChildren) {
    return (
      <QueryProvider>
        <MemoryRouter initialEntries={[initialEntry]}>{children}</MemoryRouter>
      </QueryProvider>
    )
  }

  return {
    onRunSelected,
    ...render(
      <>
        <EdaRunControls onRunSelected={onRunSelected} />
        <LocationProbe />
      </>,
      { wrapper: Wrapper },
    ),
  }
}

function currentSearch(): URLSearchParams {
  return new URLSearchParams(screen.getByTestId('location-search').textContent ?? '')
}

function runFor(
  periodKind: 'daily' | 'weekly',
  runId: string,
  from: string,
  to: string,
): EdaRunSummary {
  return {
    ...edaReadyMonthlyRun,
    run_id: runId,
    scope: { ...edaReadyMonthlyRun.scope, period_kind: periodKind, from, to },
    sections: edaReadyMonthlyRun.sections.map((section) => ({ ...section, run_id: runId })),
  }
}

afterEach(() => {
  for (const harness of harnesses.splice(0)) harness.restore()
})

describe('EdaRunControls', () => {
  it('falls back from monthly to weekly before daily and serializes the selected run', async () => {
    const weeklyRun = runFor(
      'weekly',
      'run-b02-weekly-ready',
      '2026-02-02T00:00:00',
      '2026-02-09T00:00:00',
    )
    const dailyRun = runFor(
      'daily',
      'run-b02-daily-ready',
      '2026-02-10T00:00:00',
      '2026-02-11T00:00:00',
    )
    server.use(
      http.get('/api/eda/periods', ({ request }) => {
        const periodKind = new URL(request.url).searchParams.get('period_kind') as 'daily' | 'weekly' | 'monthly'
        const items = periodKind === 'weekly' ? [weeklyRun] : periodKind === 'daily' ? [dailyRun] : []
        return HttpResponse.json({
          request_id: `req-${periodKind}`,
          period_kind: periodKind,
          items,
          next_cursor: null,
          returned_count: items.length,
        })
      }),
      http.get('/api/eda/runs/:runId', () => (
        HttpResponse.json({ request_id: 'req-weekly-run', run: weeklyRun })
      )),
    )
    const { onRunSelected } = renderControls()

    await waitFor(() => expect(onRunSelected).toHaveBeenLastCalledWith(weeklyRun))
    await waitFor(() => expect(currentSearch().get('mode')).toBe('precompute'))
    const search = currentSearch()
    expect(search.get('period_kind')).toBe('weekly')
    expect(search.get('run')).toBe(weeklyRun.run_id)
    expect(search.get('from')).toBe('2025-06-23T00:00:00')
    expect(search.get('to')).toBe('2026-07-24T09:02:05')
    expect(search.has('sensor')).toBe(false)
    expect(search.has('bucket')).toBe(false)
  })

  it('renders an actionable empty state without an implicit compute request', async () => {
    let computeRequests = 0
    server.use(
      http.get('/api/eda/periods', ({ request }) => {
        const periodKind = new URL(request.url).searchParams.get('period_kind')
        return HttpResponse.json({
          request_id: `req-${periodKind}`,
          period_kind: periodKind,
          items: [],
          next_cursor: null,
          returned_count: 0,
        })
      }),
      http.post('/api/eda/compute', () => {
        computeRequests += 1
        return HttpResponse.json(edaCacheHitResponse)
      }),
    )
    const { onRunSelected } = renderControls()

    expect(await screen.findByText('Belum ada hasil EDA precompute')).not.toBeNull()
    expect(onRunSelected).toHaveBeenLastCalledWith(null)
    expect(computeRequests).toBe(0)
  })

  it('keeps an incomplete custom datetime draft without dropping or resetting the URL range', async () => {
    const initialFrom = '2026-07-20T00:00:00'
    const initialTo = '2026-07-24T00:00:00'
    const nextFrom = '2026-07-24T00:00'
    const nextTo = '2026-07-24T09:00'
    renderControls(
      `/?mode=custom&period_kind=monthly&from=${initialFrom}&to=${initialTo}`,
    )
    const fromInput = await screen.findByLabelText('Dari') as HTMLInputElement
    const toInput = screen.getByLabelText('Sampai') as HTMLInputElement

    fireEvent.change(fromInput, { target: { value: '' } })
    expect(fromInput.value).toBe('')
    expect(currentSearch().get('from')).toBe(initialFrom)
    expect(currentSearch().get('to')).toBe(initialTo)

    fireEvent.change(fromInput, { target: { value: nextFrom } })
    expect(fromInput.value).toBe(nextFrom)
    expect(currentSearch().get('from')).toBe(initialFrom)

    fireEvent.change(toInput, { target: { value: nextTo } })
    await waitFor(() => expect(currentSearch().get('from')).toBe(`${nextFrom}:00`))
    expect(currentSearch().get('to')).toBe(`${nextTo}:00`)
    expect(fromInput.value).not.toBe('2025-06-23T00:00')
  })

  it('keeps the displayed run while custom filters are dirty and selects a cache hit without polling', async () => {
    const user = userEvent.setup()
    let computeRequests = 0
    let jobRequests = 0
    server.use(
      http.post('/api/eda/compute', () => {
        computeRequests += 1
        return HttpResponse.json(edaCacheHitResponse)
      }),
      http.get('/api/eda/jobs/:jobId', () => {
        jobRequests += 1
        return HttpResponse.json({ request_id: 'unexpected-job', job: edaRunningCustomJob })
      }),
    )
    const { onRunSelected } = renderControls()
    await waitFor(() => expect(onRunSelected).toHaveBeenCalledWith(edaReadyMonthlyRun))

    await user.click(screen.getByLabelText('Mode'))
    await user.click(screen.getByRole('option', { name: 'Rentang kustom' }))
    fireEvent.change(screen.getByLabelText('Dari'), { target: { value: '2026-02-01T00:00:00' } })
    fireEvent.change(screen.getByLabelText('Sampai'), { target: { value: '2026-02-02T00:00:00' } })

    expect(screen.getByText(/Rentang belum dihitung/)).not.toBeNull()
    expect(computeRequests).toBe(0)
    expect(onRunSelected).toHaveBeenLastCalledWith(edaReadyMonthlyRun)
    expect(currentSearch().get('run')).toBe(edaReadyMonthlyRun.run_id)

    await user.click(screen.getByRole('button', { name: 'Hitung EDA' }))
    await waitFor(() => expect(onRunSelected).toHaveBeenLastCalledWith(edaCacheHitResponse.run))
    expect(computeRequests).toBe(1)
    expect(jobRequests).toBe(0)
    await waitFor(() => expect(currentSearch().get('run')).toBe(edaCacheHitResponse.run.run_id))
  })

  it('disables duplicate submit while polling and selects the published run on success', async () => {
    const user = userEvent.setup()
    let jobRequests = 0
    const succeededJob = {
      ...edaRunningCustomJob,
      status: 'succeeded' as const,
      terminal: true,
      completed_at: '2026-07-26T07:04:00Z',
      run_id: edaPublishedCustomRun.run_id,
    }
    server.use(http.get('/api/eda/jobs/:jobId', () => {
      jobRequests += 1
      return HttpResponse.json({
        request_id: `req-job-${jobRequests}`,
        job: jobRequests === 1 ? edaRunningCustomJob : succeededJob,
      })
    }))
    const { onRunSelected } = renderControls(
      `/?mode=custom&period_kind=monthly&from=${edaRunningCustomJob.scope.from}` +
      `&to=${edaRunningCustomJob.scope.to}&run=${edaReadyMonthlyRun.run_id}`,
    )
    const submit = await screen.findByRole('button', { name: 'Hitung EDA' })

    await user.click(submit)
    expect(await screen.findByText(/Status perhitungan EDA: running/)).not.toBeNull()
    expect((submit as HTMLButtonElement).disabled).toBe(true)
    await waitFor(() => expect(onRunSelected).toHaveBeenLastCalledWith(edaPublishedCustomRun), {
      timeout: 2_500,
    })
    expect(currentSearch().get('run')).toBe(edaPublishedCustomRun.run_id)
    expect(jobRequests).toBe(2)
  })

  it('stops on a failed job and retries only after the user asks', async () => {
    const user = userEvent.setup()
    let computeRequests = 0
    let jobRequests = 0
    server.use(
      http.post('/api/eda/compute', () => {
        computeRequests += 1
        return HttpResponse.json(
          computeRequests === 1 ? edaRunningComputeResponse : edaCacheHitResponse,
          { status: computeRequests === 1 ? 202 : 200 },
        )
      }),
      http.get('/api/eda/jobs/:jobId', () => {
        jobRequests += 1
        return HttpResponse.json({
          request_id: 'req-failed-job',
          job: { ...edaFailedJob, job_id: edaRunningCustomJob.job_id },
        })
      }),
    )
    const { onRunSelected } = renderControls(
      `/?mode=custom&period_kind=monthly&from=${edaCacheHitResponse.run.scope.from}` +
      `&to=${edaCacheHitResponse.run.scope.to}&run=${edaReadyMonthlyRun.run_id}`,
    )

    await user.click(await screen.findByRole('button', { name: 'Hitung EDA' }))
    const retry = await screen.findByRole('button', { name: 'Retry' })
    const requestsAtFailure = jobRequests
    await new Promise((resolve) => globalThis.setTimeout(resolve, 1_100))
    expect(jobRequests).toBe(requestsAtFailure)
    expect(computeRequests).toBe(1)

    await user.click(retry)
    await waitFor(() => expect(onRunSelected).toHaveBeenLastCalledWith(edaCacheHitResponse.run))
    expect(computeRequests).toBe(2)
  })
})

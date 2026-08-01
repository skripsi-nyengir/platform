import { cleanup, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { queryClient } from '../app/queryClient'
import { renderApp } from '../test/renderApp'

const livePaths = [
  '/api/telemetry/latest',
  '/api/telemetry/history',
  '/api/inference-results',
  '/api/post-inference-bins',
  '/api/alerts/current',
  '/api/alert-events',
  '/api/system/status',
] as const

function liveInputs(calls: ReturnType<typeof vi.fn>['mock']['calls']): string[] {
  return calls
    .map(([input]) => new URL(String(input), 'http://localhost'))
    .filter((url) => livePaths.some((path) => url.pathname === path))
    .map((url) => {
      url.searchParams.sort()
      return `${url.pathname}?${url.searchParams}`
    })
    .toSorted()
}

afterEach(() => {
  queryClient.clear()
  vi.restoreAllMocks()
})

describe('live page API parity', () => {
  it('sends identical live API inputs from overview and sensor detail', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    const search = 'range=custom&from=2026-07-31T02:00:00&to=2026-07-31T08:00:00'
    const overview = renderApp(`/?${search}`)
    expect(await screen.findByRole('combobox', { name: 'Range' })).toHaveValue('custom')
    await waitFor(() => expect(liveInputs(fetchSpy.mock.calls)).toHaveLength(7))
    const overviewInputs = liveInputs(fetchSpy.mock.calls)

    overview.unmount()
    cleanup()
    queryClient.clear()
    fetchSpy.mockClear()

    renderApp(`/sensors/b02f3872-ruang-produksi?${search}`)
    expect(await screen.findByRole('combobox', { name: 'Range' })).toHaveValue('custom')
    await waitFor(() => expect(liveInputs(fetchSpy.mock.calls)).toHaveLength(7))

    expect(liveInputs(fetchSpy.mock.calls)).toEqual(overviewInputs)
  })
})

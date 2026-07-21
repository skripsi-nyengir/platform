import { act, renderHook, waitFor } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { server } from '../../mocks/node'
import { setMockScenario } from '../../mocks/state'
import {
  createQueryTestHarness,
  type QueryTestHarness,
} from '../../test/queryTestUtils'
import { createAlertLifecycleCommand } from './alertCommand'
import { useAlertEventsQuery, useCurrentAlertsQuery } from './queries'
import { useAlertLifecycleMutation } from './useAlertLifecycleMutation'

const eventTs = '2026-07-19T10:31:00Z'

let harness: QueryTestHarness

beforeEach(() => {
  harness = createQueryTestHarness()
})

afterEach(() => {
  harness.restore()
  vi.restoreAllMocks()
})

function acknowledgementResponse(note: string | undefined) {
  return {
    request_id: 'req-acknowledge',
    alert_id: 'alert_n4_active',
    status: 'acknowledged',
    event: {
      event_id: 'event_n4_ack_test',
      alert_id: 'alert_n4_active',
      event_ts: eventTs,
      event_type: 'acknowledged',
      device_id: 'n4',
      actor: 'operator',
      note: note ?? null,
      inference_result_window_start_ts: null,
      inference_result_window_end_ts: null,
      inference_model_version: null,
    },
    idempotent_replay: false,
  }
}

describe('alert queries', () => {
  it('normalizes primitive keys and polls only current alerts every 10 seconds', async () => {
    const current = renderHook(() => useCurrentAlertsQuery(), { wrapper: harness.wrapper })
    const events = renderHook(() => useAlertEventsQuery(), { wrapper: harness.wrapper })

    await waitFor(() => expect(current.result.current.isSuccess).toBe(true))
    await waitFor(() => expect(events.result.current.isSuccess).toBe(true))

    const currentKey = ['alerts', 'current', null, null, 1, 25] as const
    const eventsKey = ['alerts', 'events', null, null, null, null, 200, null] as const
    const currentQuery = harness.queryClient.getQueryCache().find({ queryKey: currentKey })
    const eventsQuery = harness.queryClient.getQueryCache().find({ queryKey: eventsKey })

    expect(currentQuery?.options).toHaveProperty('refetchInterval', 10_000)
    expect(eventsQuery?.options).not.toHaveProperty('refetchInterval')
    expect([...currentKey, ...eventsKey].every((value) =>
      value === null || typeof value === 'string' || typeof value === 'number',
    )).toBe(true)
  })
})

describe('createAlertLifecycleCommand', () => {
  it('creates identity and timestamp once and includes a supplied note in one stable body', () => {
    const uuid = vi.spyOn(crypto, 'randomUUID').mockReturnValue('550e8400-e29b-41d4-a716-446655440000')
    const timestamp = vi.spyOn(Date.prototype, 'toISOString').mockReturnValue(eventTs)

    const command = createAlertLifecycleCommand('alert-1', 'acknowledge', 'Checked')

    expect(command).toEqual({
      alertId: 'alert-1',
      action: 'acknowledge',
      body: {
        command_id: '550e8400-e29b-41d4-a716-446655440000',
        event_ts: eventTs,
        note: 'Checked',
      },
    })
    expect(uuid).toHaveBeenCalledOnce()
    expect(timestamp).toHaveBeenCalledOnce()
  })

  it('omits note when it is not supplied', () => {
    vi.spyOn(crypto, 'randomUUID').mockReturnValue('550e8400-e29b-41d4-a716-446655440000')
    vi.spyOn(Date.prototype, 'toISOString').mockReturnValue(eventTs)

    expect(createAlertLifecycleCommand('alert-1', 'resolve').body).not.toHaveProperty('note')
  })
})

describe('useAlertLifecycleMutation', () => {
  it('keeps confirmed current-alert cache unchanged while the command is pending', async () => {
    const confirmed = { items: [{ alert_id: 'alert_n4_active', status: 'detected' }] }
    harness.queryClient.setQueryData(['alerts', 'current'], confirmed)
    let releaseResponse: () => void = () => {
      throw new Error('Response gate was not initialized')
    }
    const responseGate = new Promise<void>((resolve) => {
      releaseResponse = resolve
    })
    server.use(
      http.post(`${window.location.origin}/api/alerts/:alertId/acknowledge`, async () => {
        await responseGate
        return HttpResponse.json(acknowledgementResponse('Checked'))
      }),
    )
    const invalidation = vi.spyOn(harness.queryClient, 'invalidateQueries')
    const mutation = renderHook(() => useAlertLifecycleMutation(), { wrapper: harness.wrapper })
    const command = {
      alertId: 'alert_n4_active',
      action: 'acknowledge' as const,
      body: { command_id: 'command-1', event_ts: eventTs, note: 'Checked' },
    }

    act(() => mutation.result.current.mutate(command))
    await waitFor(() => expect(mutation.result.current.isPending).toBe(true))
    expect(harness.queryClient.getQueryData(['alerts', 'current'])).toBe(confirmed)

    releaseResponse()
    await waitFor(() => expect(mutation.result.current.isSuccess).toBe(true))
    expect(invalidation).toHaveBeenCalledWith({ queryKey: ['alerts', 'current'] })
    expect(invalidation).toHaveBeenCalledWith({ queryKey: ['alerts', 'events'] })
  })

  it('retains exact failed variables, retries the saved body, and clears variables on reset', async () => {
    const requestBodies: string[] = []
    let attempt = 0
    server.use(
      http.post(`${window.location.origin}/api/alerts/:alertId/acknowledge`, async ({ request }) => {
        requestBodies.push(await request.text())
        attempt += 1
        if (attempt === 1) {
          return HttpResponse.json({ message: 'temporary failure' }, { status: 503 })
        }
        return HttpResponse.json(acknowledgementResponse('Retry unchanged'))
      }),
    )
    const invalidation = vi.spyOn(harness.queryClient, 'invalidateQueries')
    const mutation = renderHook(() => useAlertLifecycleMutation(), { wrapper: harness.wrapper })
    const command = {
      alertId: 'alert_n4_active',
      action: 'acknowledge' as const,
      body: { command_id: 'command-retry', event_ts: eventTs, note: 'Retry unchanged' },
    }

    act(() => mutation.result.current.mutate(command))
    await waitFor(() => expect(mutation.result.current.isError).toBe(true))
    expect(mutation.result.current.variables).toBe(command)
    const savedCommand = mutation.result.current.variables
    if (savedCommand === undefined) throw new Error('Expected failed mutation variables')

    act(() => mutation.result.current.mutate(savedCommand))
    await waitFor(() => expect(mutation.result.current.isSuccess).toBe(true))
    expect(mutation.result.current.variables).toBe(command)
    expect(requestBodies).toEqual([JSON.stringify(command.body), JSON.stringify(command.body)])
    expect(invalidation).toHaveBeenCalledWith({ queryKey: ['alerts', 'current'] })
    expect(invalidation).toHaveBeenCalledWith({ queryKey: ['alerts', 'events'] })

    act(() => mutation.result.current.reset())
    await waitFor(() => expect(mutation.result.current.variables).toBeUndefined())
  })

  it('invalidates confirmed current alerts but not event history after a lifecycle conflict', async () => {
    setMockScenario('active-anomaly')
    const invalidation = vi.spyOn(harness.queryClient, 'invalidateQueries')
    const mutation = renderHook(() => useAlertLifecycleMutation(), { wrapper: harness.wrapper })
    const command = {
      alertId: 'alert_n4_active',
      action: 'resolve' as const,
      body: { command_id: 'command-conflict', event_ts: eventTs },
    }

    act(() => mutation.result.current.mutate(command))
    await waitFor(() => expect(mutation.result.current.isError).toBe(true))

    expect(invalidation).toHaveBeenCalledWith({ queryKey: ['alerts', 'current'] })
    expect(invalidation).not.toHaveBeenCalledWith({ queryKey: ['alerts', 'events'] })
  })
})

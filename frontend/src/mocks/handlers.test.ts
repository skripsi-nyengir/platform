import { afterEach, describe, expect, it, vi } from 'vitest'
import { getSystemStatus } from '../api/systemHealth'
import {
  AlertMutationResponseSchema,
  AlertEventsResponseSchema,
  CurrentAlertsResponseSchema,
} from '../contracts/alerts'
import { ProblemDetailsSchema } from '../contracts/common'
import {
  EdaCorrelationResponseSchema,
  EdaDistributionResponseSchema,
  EdaSummaryResponseSchema,
} from '../contracts/eda'
import { InferenceResponseSchema } from '../contracts/inference'
import {
  ModelEvaluationDetailSchema,
  ModelEvaluationsResponseSchema,
} from '../contracts/modelEvaluation'
import {
  LivenessResponseSchema,
  ReadinessResponseSchema,
  SystemStatusResponseSchema,
} from '../contracts/systemHealth'
import {
  LatestTelemetryResponseSchema,
  TelemetryHistoryResponseSchema,
} from '../contracts/telemetry'
import { server } from './node'
import { scenarioFromSearch } from './scenario'
import { mockState, resetMockState, setMockScenario } from './state'

const from = '2026-07-19T10:00:00Z'
const to = '2026-07-19T10:30:00Z'
const command = {
  command_id: '550e8400-e29b-41d4-a716-446655440000',
  event_ts: '2026-07-19T10:31:00Z',
  note: 'Checked on site',
}

function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(new URL(path, window.location.origin), init)
}

function postCommand(alertId: string, action: 'acknowledge' | 'resolve', body = command) {
  return apiFetch(`/api/alerts/${encodeURIComponent(alertId)}/${action}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  })
}

const normalEndpointCases = [
  {
    name: 'latest telemetry',
    path: '/api/telemetry/latest',
    schema: LatestTelemetryResponseSchema,
    expectedStatus: 200,
  },
  {
    name: 'telemetry history',
    path: `/api/telemetry/history?device_id=n1&from=${from}&to=${to}&bucket=5m&limit=2`,
    schema: TelemetryHistoryResponseSchema,
    expectedStatus: 200,
  },
  {
    name: 'inference results',
    path: `/api/inference-results?device_id=n1&from=${from}&to=${to}&bucket=raw&limit=2`,
    schema: InferenceResponseSchema,
    expectedStatus: 200,
  },
  {
    name: 'alert events',
    path: '/api/alert-events?limit=2',
    schema: AlertEventsResponseSchema,
    expectedStatus: 200,
  },
  {
    name: 'current alerts',
    path: '/api/alerts/current?page=1&page_size=2',
    schema: CurrentAlertsResponseSchema,
    expectedStatus: 200,
  },
  {
    name: 'acknowledge alert',
    path: '/api/alerts/missing-alert/acknowledge',
    schema: ProblemDetailsSchema,
    expectedStatus: 404,
    init: {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(command),
    },
  },
  {
    name: 'resolve alert',
    path: '/api/alerts/missing-alert/resolve',
    schema: ProblemDetailsSchema,
    expectedStatus: 404,
    init: {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(command),
    },
  },
  {
    name: 'EDA summary',
    path: `/api/eda/summary?from=${from}&to=${to}&bucket=5m`,
    schema: EdaSummaryResponseSchema,
    expectedStatus: 200,
  },
  {
    name: 'EDA distributions',
    path: `/api/eda/distributions?from=${from}&to=${to}&field=temperature_c&bins=5`,
    schema: EdaDistributionResponseSchema,
    expectedStatus: 200,
  },
  {
    name: 'EDA correlation',
    path: `/api/eda/correlation?from=${from}&to=${to}&x_field=temperature_c&y_field=relative_humidity_pct&max_points=100`,
    schema: EdaCorrelationResponseSchema,
    expectedStatus: 200,
  },
  {
    name: 'model evaluations',
    path: '/api/model-evaluations?page=1&page_size=1',
    schema: ModelEvaluationsResponseSchema,
    expectedStatus: 200,
  },
  {
    name: 'model evaluation detail',
    path: '/api/model-evaluations/model-v1',
    schema: ModelEvaluationDetailSchema,
    expectedStatus: 200,
  },
  {
    name: 'system status',
    path: '/api/system/status',
    schema: SystemStatusResponseSchema,
    expectedStatus: 200,
  },
  {
    name: 'liveness',
    path: '/health',
    schema: LivenessResponseSchema,
    expectedStatus: 200,
  },
  {
    name: 'readiness',
    path: '/ready',
    schema: ReadinessResponseSchema,
    expectedStatus: 200,
  },
] as const

const invalidQueryCases = [
  { name: 'latest invalid sensor', path: '/api/telemetry/latest?device_id=n7' },
  {
    name: 'telemetry invalid bucket',
    path: `/api/telemetry/history?device_id=n1&from=${from}&to=${to}&bucket=2m`,
  },
  {
    name: 'telemetry over-bound limit',
    path: `/api/telemetry/history?device_id=n1&from=${from}&to=${to}&limit=5001`,
  },
  {
    name: 'telemetry nonnumeric limit',
    path: `/api/telemetry/history?device_id=n1&from=${from}&to=${to}&limit=invalid`,
  },
  {
    name: 'telemetry missing range',
    path: `/api/telemetry/history?device_id=n1&to=${to}`,
  },
  {
    name: 'telemetry malformed range',
    path: `/api/telemetry/history?device_id=n1&from=not-a-time&to=${to}`,
  },
  {
    name: 'telemetry reversed range',
    path: `/api/telemetry/history?device_id=n1&from=${to}&to=${from}`,
  },
  {
    name: 'inference invalid sensor',
    path: `/api/inference-results?device_id=n7&from=${from}&to=${to}`,
  },
  {
    name: 'inference under-bound limit',
    path: `/api/inference-results?device_id=n1&from=${from}&to=${to}&limit=0`,
  },
  {
    name: 'inference missing range',
    path: `/api/inference-results?device_id=n1&from=${from}`,
  },
  { name: 'alert events invalid sensor', path: '/api/alert-events?device_id=n7' },
  { name: 'alert events over-bound limit', path: '/api/alert-events?limit=201' },
  { name: 'alert events malformed range', path: '/api/alert-events?from=not-a-time' },
  {
    name: 'alert events reversed range',
    path: `/api/alert-events?from=${to}&to=${from}`,
  },
  { name: 'current alerts invalid status', path: '/api/alerts/current?status=open' },
  { name: 'current alerts under-bound page', path: '/api/alerts/current?page=0' },
  { name: 'current alerts over-bound page size', path: '/api/alerts/current?page_size=101' },
  {
    name: 'EDA summary invalid bucket',
    path: `/api/eda/summary?from=${from}&to=${to}&bucket=2m`,
  },
  { name: 'EDA summary missing range', path: `/api/eda/summary?to=${to}` },
  {
    name: 'EDA summary reversed range',
    path: `/api/eda/summary?from=${to}&to=${from}`,
  },
  {
    name: 'EDA distribution invalid field',
    path: `/api/eda/distributions?from=${from}&to=${to}&field=pressure&bins=20`,
  },
  {
    name: 'EDA distribution bins below five',
    path: `/api/eda/distributions?from=${from}&to=${to}&field=score&bins=4`,
  },
  {
    name: 'EDA distribution bins above one hundred',
    path: `/api/eda/distributions?from=${from}&to=${to}&field=score&bins=101`,
  },
  {
    name: 'EDA distribution missing range',
    path: `/api/eda/distributions?from=${from}&field=score`,
  },
  {
    name: 'EDA correlation invalid sensor',
    path: `/api/eda/correlation?device_id=n7&from=${from}&to=${to}&x_field=temperature_c&y_field=score`,
  },
  {
    name: 'EDA correlation max points below one hundred',
    path: `/api/eda/correlation?from=${from}&to=${to}&x_field=temperature_c&y_field=score&max_points=99`,
  },
  {
    name: 'EDA correlation max points above five thousand',
    path: `/api/eda/correlation?from=${from}&to=${to}&x_field=temperature_c&y_field=score&max_points=5001`,
  },
  {
    name: 'EDA correlation equal fields',
    path: `/api/eda/correlation?from=${from}&to=${to}&x_field=score&y_field=score`,
  },
  {
    name: 'EDA correlation missing range',
    path: `/api/eda/correlation?to=${to}&x_field=temperature_c&y_field=score`,
  },
  { name: 'model evaluations under-bound page', path: '/api/model-evaluations?page=0' },
  {
    name: 'model evaluations over-bound page size',
    path: '/api/model-evaluations?page_size=51',
  },
] as const

afterEach(() => {
  server.resetHandlers()
  resetMockState()
})

describe('scenario selection', () => {
  it('accepts all named scenarios and defaults every other value to normal', () => {
    const scenarios = [
      'normal',
      'active-anomaly',
      'stale',
      'offline',
      'data-gap',
      'empty',
      'timeout',
      'server-error',
    ] as const

    for (const scenario of scenarios) {
      expect(scenarioFromSearch(`?__scenario=${scenario}`)).toBe(scenario)
    }
    expect(scenarioFromSearch('?__scenario=unsupported')).toBe('normal')
    expect(scenarioFromSearch('')).toBe('normal')
  })
})

describe('normal endpoint matrix', () => {
  it.each(normalEndpointCases)('serves schema-valid $name', async ({ path, schema, expectedStatus, ...testCase }) => {
    const response = await apiFetch(path, 'init' in testCase ? testCase.init : undefined)
    expect(response.status).toBe(expectedStatus)
    const body: unknown = await response.json()
    expect(() => schema.parse(body)).not.toThrow()
  })

  it('honors filters, bounds, page metadata, cursors, bins, max points, and model version', async () => {
    const latest = LatestTelemetryResponseSchema.parse(
      await (await apiFetch('/api/telemetry/latest?device_id=n2')).json(),
    )
    expect(latest.sensors.map(({ device_id }) => device_id)).toEqual(['n2'])

    const history = TelemetryHistoryResponseSchema.parse(
      await (
        await apiFetch(
          `/api/telemetry/history?device_id=n1&from=${from}&to=${to}&bucket=5m&limit=2`,
        )
      ).json(),
    )
    expect(history).toMatchObject({
      device_id: 'n1',
      from,
      to,
      bucket: '5m',
      returned_count: 2,
      next_cursor: 'telemetry:2',
    })
    expect(history.points.every((point) => point.ts >= from && point.ts < to)).toBe(true)
    const nextHistory = TelemetryHistoryResponseSchema.parse(
      await (
        await apiFetch(
          `/api/telemetry/history?device_id=n1&from=${from}&to=${to}&bucket=5m&limit=2&cursor=telemetry%3A2`,
        )
      ).json(),
    )
    expect(nextHistory.points[0]?.ts).not.toBe(history.points[0]?.ts)

    const inference = InferenceResponseSchema.parse(
      await (
        await apiFetch(
          `/api/inference-results?device_id=n1&from=${from}&to=${to}&bucket=raw&limit=2&model_version=model-v2`,
        )
      ).json(),
    )
    expect(inference).toMatchObject({
      model_version: 'model-v2',
      returned_count: 2,
      next_cursor: 'inference:2',
    })
    expect(inference.points.every((point) => point.model_version === 'model-v2')).toBe(true)

    const distribution = EdaDistributionResponseSchema.parse(
      await (
        await apiFetch(`/api/eda/distributions?from=${from}&to=${to}&field=score&bins=5`)
      ).json(),
    )
    expect(distribution).toMatchObject({ field: 'score' })
    expect(distribution.bins).toHaveLength(5)

    const correlation = EdaCorrelationResponseSchema.parse(
      await (
        await apiFetch(
          `/api/eda/correlation?from=${from}&to=${to}&x_field=score&y_field=temperature_c&max_points=100`,
        )
      ).json(),
    )
    expect(correlation).toMatchObject({
      x_field: 'score',
      y_field: 'temperature_c',
      next_cursor: null,
    })
    expect(correlation.points).toHaveLength(6)

    const models = ModelEvaluationsResponseSchema.parse(
      await (await apiFetch('/api/model-evaluations?page=2&page_size=1')).json(),
    )
    expect(models).toMatchObject({ page: 2, page_size: 1, total: 2 })
    expect(models.items[0]?.version).toBe('model-v1')
  })

  it('decodes dynamic path segments before reporting missing resources', async () => {
    const response = await apiFetch('/api/model-evaluations/missing%2Fversion')
    expect(response.status).toBe(404)
    expect(ProblemDetailsSchema.parse(await response.json())).toMatchObject({
      request_id: 'req_model_not_found',
      detail: 'Model evaluation missing/version was not found',
    })

    const percentResponse = await apiFetch('/api/model-evaluations/missing%25version')
    expect(percentResponse.status).toBe(404)
    expect(ProblemDetailsSchema.parse(await percentResponse.json())).toMatchObject({
      request_id: 'req_model_not_found',
      detail: 'Model evaluation missing%version was not found',
    })
  })

  it('uses half-open point and event timestamp ranges', async () => {
    const history = TelemetryHistoryResponseSchema.parse(
      await (
        await apiFetch(
          '/api/telemetry/history?device_id=n1&from=2026-07-19T10%3A00%3A00Z&to=2026-07-19T10%3A25%3A00Z&limit=500',
        )
      ).json(),
    )
    expect(history.points.map(({ ts }) => ts)).not.toContain('2026-07-19T10:25:00Z')

    setMockScenario('active-anomaly')
    const events = AlertEventsResponseSchema.parse(
      await (
        await apiFetch(
          '/api/alert-events?from=2026-07-19T10%3A00%3A00Z&to=2026-07-19T10%3A20%3A00Z&limit=200',
        )
      ).json(),
    )
    expect(events.events).toEqual([])

    const correlation = EdaCorrelationResponseSchema.parse(
      await (
        await apiFetch(
          '/api/eda/correlation?from=2026-07-19T10%3A00%3A00Z&to=2026-07-19T10%3A25%3A00Z&x_field=temperature_c&y_field=score&max_points=100',
        )
      ).json(),
    )
    expect(correlation.points).toEqual([])
  })
})

describe('invalid query Problem Details', () => {
  it.each(invalidQueryCases)('returns 422 for $name', async ({ path }) => {
    const response = await apiFetch(path)
    expect(response.status).toBe(422)
    expect(ProblemDetailsSchema.parse(await response.json())).toMatchObject({
      status: 422,
      request_id: 'req_invalid_query',
    })
  })
})

describe('named scenario semantics', () => {
  it('serves the n4 threshold breach, detected current alert, and score-lane marker', async () => {
    setMockScenario('active-anomaly')

    const inference = InferenceResponseSchema.parse(
      await (
        await apiFetch(
          `/api/inference-results?device_id=n4&from=${from}&to=${to}&bucket=raw&limit=10`,
        )
      ).json(),
    )
    expect(inference.points.at(-1)).toMatchObject({
      score: 0.96,
      threshold: 0.8,
      is_anomaly: true,
    })

    const current = CurrentAlertsResponseSchema.parse(
      await (await apiFetch('/api/alerts/current?device_id=n4&page=1&page_size=25')).json(),
    )
    expect(current.items).toEqual([
      expect.objectContaining({
        alert_id: 'alert_n4_active',
        device_id: 'n4',
        status: 'detected',
        can_acknowledge: true,
        can_resolve: false,
      }),
    ])

    const events = AlertEventsResponseSchema.parse(
      await (await apiFetch('/api/alert-events?device_id=n4&limit=200')).json(),
    )
    expect(events.events).toEqual([
      expect.objectContaining({ alert_id: 'alert_n4_active', event_type: 'detected' }),
    ])
  })

  it('keeps stale telemetry available with a valid old timestamp', async () => {
    setMockScenario('stale')
    const latest = LatestTelemetryResponseSchema.parse(
      await (await apiFetch('/api/telemetry/latest?device_id=n2')).json(),
    )
    expect(latest.sensors).toEqual([
      expect.objectContaining({
        device_id: 'n2',
        ts: '2026-07-19T10:20:00Z',
        freshness: 'stale',
        age_seconds: 600,
        availability: 'online',
      }),
    ])
    const system = SystemStatusResponseSchema.parse(
      await (await apiFetch('/api/system/status')).json(),
    )
    expect(system.telemetry).toMatchObject({ fresh_sensor_count: 5, stale_sensor_count: 1 })
  })

  it('keeps an offline sensor last timestamp and age while freshness is unknown', async () => {
    setMockScenario('offline')
    const latest = LatestTelemetryResponseSchema.parse(
      await (await apiFetch('/api/telemetry/latest?device_id=n3')).json(),
    )
    expect(latest.sensors).toEqual([
      expect.objectContaining({
        device_id: 'n3',
        ts: '2026-07-19T09:30:00Z',
        freshness: 'unknown',
        age_seconds: 3_600,
        availability: 'offline',
      }),
    ])
    const system = SystemStatusResponseSchema.parse(
      await (await apiFetch('/api/system/status')).json(),
    )
    expect(system.telemetry).toMatchObject({ fresh_sensor_count: 5, offline_sensor_count: 1 })
  })

  it('omits the missing n5 interval and marks only the first post-gap point', async () => {
    setMockScenario('data-gap')
    const history = TelemetryHistoryResponseSchema.parse(
      await (
        await apiFetch(
          `/api/telemetry/history?device_id=n5&from=${from}&to=${to}&bucket=5m&limit=20`,
        )
      ).json(),
    )
    expect(history.points.map(({ ts }) => ts)).not.toContain('2026-07-19T10:10:00Z')
    expect(history.points.find(({ ts }) => ts === '2026-07-19T10:15:00Z')).toMatchObject({
      gap_before: true,
    })
    expect(history.points.filter(({ gap_before }) => gap_before)).toHaveLength(1)

    const summary = EdaSummaryResponseSchema.parse(
      await (
        await apiFetch(`/api/eda/summary?device_id=n5&from=${from}&to=${to}&bucket=5m`)
      ).json(),
    )
    expect(summary.coverage).toMatchObject({ expected_count: 6, observed_count: 5, gap_count: 1 })
  })

  it('returns valid empty selected-filter results without emptying unaffected data', async () => {
    setMockScenario('empty')
    const latest = LatestTelemetryResponseSchema.parse(
      await (await apiFetch('/api/telemetry/latest?device_id=n6')).json(),
    )
    expect(latest.sensors).toEqual([])

    const history = TelemetryHistoryResponseSchema.parse(
      await (
        await apiFetch(
          `/api/telemetry/history?device_id=n6&from=${from}&to=${to}&bucket=raw&limit=10`,
        )
      ).json(),
    )
    expect(history).toMatchObject({ points: [], returned_count: 0, next_cursor: null })

    const inference = InferenceResponseSchema.parse(
      await (
        await apiFetch(
          `/api/inference-results?device_id=n6&from=${from}&to=${to}&bucket=raw&limit=10`,
        )
      ).json(),
    )
    expect(inference).toMatchObject({ points: [], returned_count: 0, next_cursor: null })

    const summary = EdaSummaryResponseSchema.parse(
      await (
        await apiFetch(`/api/eda/summary?device_id=n6&from=${from}&to=${to}&bucket=raw`)
      ).json(),
    )
    expect(summary).toMatchObject({
      scope: { device_ids: ['n6'] },
      coverage: { expected_count: 0, observed_count: 0, coverage_pct: 0, gap_count: 0 },
      sensor_comparison: [],
      candidate_outliers: [],
    })

    const distribution = EdaDistributionResponseSchema.parse(
      await (
        await apiFetch(
          `/api/eda/distributions?device_id=n6&from=${from}&to=${to}&field=score&bins=5`,
        )
      ).json(),
    )
    expect(distribution).toMatchObject({ sample_count: 0, bins: [] })

    const correlation = EdaCorrelationResponseSchema.parse(
      await (
        await apiFetch(
          `/api/eda/correlation?device_id=n6&from=${from}&to=${to}&x_field=temperature_c&y_field=score&max_points=100`,
        )
      ).json(),
    )
    expect(correlation).toMatchObject({
      sample_count: 0,
      correlation: null,
      points: [],
      next_cursor: null,
    })

    const unaffected = LatestTelemetryResponseSchema.parse(
      await (await apiFetch('/api/telemetry/latest?device_id=n1')).json(),
    )
    expect(unaffected.sensors).toHaveLength(1)
  })

  it(
    'delays the selected timeout endpoint beyond the client default timeout',
    async () => {
      setMockScenario('timeout')
      const interceptedFetch = globalThis.fetch
      vi.stubGlobal(
        'fetch',
        (input: RequestInfo | URL, init?: RequestInit) =>
          interceptedFetch(new URL(String(input), window.location.origin), init),
      )
      const startedAt = performance.now()

      try {
        await expect(getSystemStatus()).rejects.toMatchObject({
          kind: 'timeout',
          message: 'Request timed out after 8000 ms',
        })
        expect(performance.now() - startedAt).toBeGreaterThanOrEqual(7_900)
      } finally {
        vi.unstubAllGlobals()
      }
    },
    10_000,
  )

  it('returns fixed Problem Details for the selected server-error endpoint', async () => {
    setMockScenario('server-error')
    const response = await apiFetch('/api/system/status')
    expect(response.status).toBe(503)
    expect(ProblemDetailsSchema.parse(await response.json())).toEqual({
      type: 'https://example.invalid/problems/mock-service-unavailable',
      title: 'Mock service unavailable',
      status: 503,
      detail: 'The deterministic mock system status endpoint failed',
      instance: '/api/system/status',
      request_id: 'req_server_error',
    })
  })
})

describe('active anomaly lifecycle', () => {
  it('rejects resolving a detected alert without appending history', async () => {
    setMockScenario('active-anomaly')
    const response = await postCommand('alert_n4_active', 'resolve')
    expect(response.status).toBe(409)
    expect(ProblemDetailsSchema.parse(await response.json())).toMatchObject({
      request_id: 'req_direct_resolve',
      status: 409,
    })
    expect(mockState.events).toHaveLength(1)
  })

  it('acknowledges once, appends immutable ordered history, and derives current state', async () => {
    setMockScenario('active-anomaly')
    const response = await postCommand('alert_n4_active', 'acknowledge')
    expect(response.status).toBe(200)
    const acknowledgement = AlertMutationResponseSchema.parse(await response.json())
    expect(acknowledgement).toMatchObject({
      request_id: 'req_acknowledge',
      alert_id: 'alert_n4_active',
      status: 'acknowledged',
      idempotent_replay: false,
      event: { event_id: 'event_n4_ack_001', note: command.note },
    })
    expect(mockState.events.map(({ event_type }) => event_type)).toEqual([
      'detected',
      'acknowledged',
    ])
    expect(Object.isFrozen(mockState.events[1])).toBe(true)

    const current = CurrentAlertsResponseSchema.parse(
      await (
        await apiFetch('/api/alerts/current?device_id=n4&status=acknowledged&page=1&page_size=25')
      ).json(),
    )
    expect(current.items).toEqual([
      expect.objectContaining({
        status: 'acknowledged',
        latest_event_id: 'event_n4_ack_001',
        can_acknowledge: false,
        can_resolve: true,
      }),
    ])

    const firstPage = AlertEventsResponseSchema.parse(
      await (
        await apiFetch(
          '/api/alert-events?alert_id=alert_n4_active&device_id=n4&from=2026-07-19T10%3A00%3A00Z&to=2026-07-19T10%3A32%3A00Z&limit=1',
        )
      ).json(),
    )
    expect(firstPage).toMatchObject({ returned_count: 1, next_cursor: 'alert-events:1' })
    expect(firstPage.events[0]?.event_type).toBe('detected')
    const secondPage = AlertEventsResponseSchema.parse(
      await (
        await apiFetch(
          '/api/alert-events?alert_id=alert_n4_active&device_id=n4&from=2026-07-19T10%3A00%3A00Z&to=2026-07-19T10%3A32%3A00Z&limit=1&cursor=alert-events%3A1',
        )
      ).json(),
    )
    expect(secondPage.events[0]?.event_type).toBe('acknowledged')
  })

  it('resolves only after acknowledgement and derives resolved current state', async () => {
    setMockScenario('active-anomaly')
    await postCommand('alert_n4_active', 'acknowledge')
    const resolutionCommand = {
      command_id: '550e8400-e29b-41d4-a716-446655440001',
      event_ts: '2026-07-19T10:32:00Z',
      note: 'Condition cleared',
    }
    const response = await postCommand('alert_n4_active', 'resolve', resolutionCommand)
    expect(AlertMutationResponseSchema.parse(await response.json())).toMatchObject({
      request_id: 'req_resolve',
      status: 'resolved',
      idempotent_replay: false,
      event: { event_id: 'event_n4_resolve_001', note: resolutionCommand.note },
    })
    expect(mockState.events.map(({ event_type }) => event_type)).toEqual([
      'detected',
      'acknowledged',
      'resolved',
    ])

    const current = CurrentAlertsResponseSchema.parse(
      await (
        await apiFetch('/api/alerts/current?device_id=n4&status=resolved&page=1&page_size=25')
      ).json(),
    )
    expect(current.items[0]).toMatchObject({
      status: 'resolved',
      latest_event_id: 'event_n4_resolve_001',
      can_acknowledge: false,
      can_resolve: false,
    })
  })

  it('replays an identical command with its original event and no append', async () => {
    setMockScenario('active-anomaly')
    const first = AlertMutationResponseSchema.parse(
      await (await postCommand('alert_n4_active', 'acknowledge')).json(),
    )
    const eventCount = mockState.events.length
    const replay = AlertMutationResponseSchema.parse(
      await (await postCommand('alert_n4_active', 'acknowledge')).json(),
    )
    expect(replay).toEqual({ ...first, idempotent_replay: true })
    expect(mockState.events).toHaveLength(eventCount)
  })

  it('rejects command ID reuse with a conflicting alert, action, timestamp, or note', async () => {
    setMockScenario('active-anomaly')
    await postCommand('alert_n4_active', 'acknowledge')
    const conflicts = [
      postCommand('another-alert', 'acknowledge'),
      postCommand('alert_n4_active', 'resolve'),
      postCommand('alert_n4_active', 'acknowledge', {
        ...command,
        event_ts: '2026-07-19T10:31:01Z',
      }),
      postCommand('alert_n4_active', 'acknowledge', { ...command, note: 'Different note' }),
    ]

    for (const pendingResponse of conflicts) {
      const response = await pendingResponse
      expect(response.status).toBe(409)
      expect(ProblemDetailsSchema.parse(await response.json())).toMatchObject({
        request_id: 'req_command_conflict',
        status: 409,
      })
    }
    expect(mockState.events).toHaveLength(2)
  })

  it('reset clears accepted commands and restores a fresh cloned scenario seed', async () => {
    setMockScenario('active-anomaly')
    const originalSeed = mockState.events[0]
    await postCommand('alert_n4_active', 'acknowledge')
    expect(mockState.acceptedCommands.size).toBe(1)

    resetMockState('active-anomaly')

    expect(mockState.acceptedCommands.size).toBe(0)
    expect(mockState.events).toEqual([
      expect.objectContaining({ event_id: 'event_n4_detected', event_type: 'detected' }),
    ])
    expect(mockState.events[0]).not.toBe(originalSeed)
    expect(Object.isFrozen(mockState.events[0])).toBe(true)
  })
})

describe('fixture schema guard', () => {
  it('keeps every populated accepted lifecycle response schema-valid', async () => {
    setMockScenario('active-anomaly')
    await postCommand('alert_n4_active', 'acknowledge')
    await postCommand('alert_n4_active', 'resolve', {
      command_id: '550e8400-e29b-41d4-a716-446655440001',
      event_ts: '2026-07-19T10:32:00Z',
      note: 'Condition cleared',
    })

    expect(mockState.acceptedCommands.size).toBe(2)
    for (const response of mockState.acceptedCommands.values()) {
      expect(AlertMutationResponseSchema.safeParse(response).success).toBe(true)
    }
  })
})

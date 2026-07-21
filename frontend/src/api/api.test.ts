import { afterEach, describe, expect, it, vi } from 'vitest'
import { z } from 'zod'
import { ApiError } from './errors'
import { requestJson } from './http'
import { getLatestTelemetry, getTelemetryHistory } from './telemetry'
import { getInferenceResults } from './inference'
import {
  acknowledgeAlert,
  getAlertEvents,
  getCurrentAlerts,
  resolveAlert,
} from './alerts'
import { getEdaCorrelation, getEdaDistributions, getEdaSummary } from './eda'
import { getModelEvaluation, getModelEvaluations } from './modelEvaluations'
import { getLiveness, getReadiness, getSystemStatus } from './systemHealth'

const from = '2026-07-19T09:00:00Z'
const to = '2026-07-19T10:00:00Z'

function jsonResponse(body: object, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

const responsesByPath: Record<string, object> = {
  '/api/telemetry/latest?device_id=n1': {
    request_id: 'req-latest',
    generated_at: to,
    sensors: [
      {
        device_id: 'n1',
        ts: to,
        temperature_c: 25,
        relative_humidity_pct: 70,
        freshness: 'fresh',
        age_seconds: 0,
        availability: 'online',
      },
    ],
  },
  [`/api/telemetry/history?device_id=n1&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&bucket=1m&limit=2000&cursor=next%2Fpage`]: {
    request_id: 'req-history',
    device_id: 'n1',
    from,
    to,
    bucket: '1m',
    points: [],
    next_cursor: null,
    returned_count: 0,
  },
  [`/api/inference-results?device_id=n1&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&bucket=raw&limit=500&model_version=model+v1`]: {
    request_id: 'req-inference',
    device_id: 'n1',
    model_version: 'model v1',
    points: [],
    next_cursor: null,
    returned_count: 0,
  },
  [`/api/alert-events?alert_id=alert+1&device_id=n4&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&limit=200&cursor=event%2F2`]: {
    request_id: 'req-events',
    events: [],
    next_cursor: null,
    returned_count: 0,
  },
  '/api/alerts/current?device_id=n4&status=acknowledged&page=2&page_size=100': {
    request_id: 'req-current',
    generated_at: to,
    items: [],
    page: 2,
    page_size: 100,
    total: 0,
  },
  '/api/alerts/alert%2F1/acknowledge': {
    request_id: 'req-ack',
    alert_id: 'alert/1',
    status: 'acknowledged',
    event: {
      event_id: 'event-1',
      alert_id: 'alert/1',
      event_ts: to,
      event_type: 'acknowledged',
      device_id: 'n4',
      actor: 'operator',
      note: null,
      inference_result_window_start_ts: null,
      inference_result_window_end_ts: null,
      inference_model_version: null,
    },
    idempotent_replay: false,
  },
  '/api/alerts/alert%2F1/resolve': {
    request_id: 'req-resolve',
    alert_id: 'alert/1',
    status: 'resolved',
    event: {
      event_id: 'event-2',
      alert_id: 'alert/1',
      event_ts: to,
      event_type: 'resolved',
      device_id: 'n4',
      actor: 'operator',
      note: null,
      inference_result_window_start_ts: null,
      inference_result_window_end_ts: null,
      inference_model_version: null,
    },
    idempotent_replay: false,
  },
  [`/api/eda/summary?device_id=n2&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&bucket=15m`]: {
    request_id: 'req-eda-summary',
    scope: { device_ids: ['n2'], from, to, bucket: '15m' },
    coverage: { expected_count: 0, observed_count: 0, coverage_pct: 0, gap_count: 0 },
    missingness: [],
    sensor_comparison: [],
    candidate_outliers: [],
  },
  [`/api/eda/distributions?device_id=n2&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&field=score&bins=5`]: {
    request_id: 'req-distribution',
    field: 'score',
    sample_count: 1,
    summary: { min: 0, max: 0, mean: 0, median: 0, p05: 0, p95: 0 },
    bins: [{ start: 0, end: 1, count: 1 }],
  },
  [`/api/eda/correlation?device_id=n2&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&x_field=temperature_c&y_field=score&max_points=100&cursor=point%2F2`]: {
    request_id: 'req-correlation',
    x_field: 'temperature_c',
    y_field: 'score',
    sample_count: 0,
    correlation: null,
    points: [],
    next_cursor: null,
  },
  '/api/model-evaluations?page=2&page_size=50': {
    request_id: 'req-models',
    items: [],
    page: 2,
    page_size: 50,
    total: 0,
  },
  '/api/model-evaluations/model%2Fv1': {
    request_id: 'req-model',
    version: 'model/v1',
    created_at: to,
    evaluation_period: '2026-07-01 to 2026-07-18',
    model_hash: null,
    preprocessing_hash: null,
    threshold_hash: null,
    has_labeled_ground_truth: false,
    available_metrics: ['mae'],
    metrics: { mae: 0.12 },
    notes: null,
  },
  '/api/system/status': {
    request_id: 'req-system',
    checked_at: to,
    overall_observation: 'All observed services ready',
    services: [],
    telemetry: {
      latest_ts: null,
      age_seconds: null,
      fresh_sensor_count: 0,
      stale_sensor_count: 0,
      offline_sensor_count: 0,
    },
  },
  '/health': { status: 'alive', request_id: 'req-health', checked_at: to },
  '/ready': {
    status: 'ready',
    request_id: 'req-ready',
    checked_at: to,
    dependencies: [{ name: 'database', status: 'ready', detail: 'Connected' }],
  },
}

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('endpoint adapters', () => {
  it('constructs every endpoint from relative paths with encoded, validated query values', async () => {
    const fetchMock = vi.fn<
      (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
    >((input) => {
      const path = String(input)
      const response = responsesByPath[path]
      if (!response) return Promise.reject(new Error(`Unexpected request: ${path}`))
      return Promise.resolve(jsonResponse(response))
    })
    vi.stubGlobal('fetch', fetchMock)

    await getLatestTelemetry('n1')
    await getTelemetryHistory({
      deviceId: 'n1',
      from,
      to,
      bucket: '1m',
      limit: 2_000,
      cursor: 'next/page',
    })
    await getInferenceResults({
      deviceId: 'n1',
      from,
      to,
      modelVersion: 'model v1',
    })
    await getAlertEvents({
      alertId: 'alert 1',
      deviceId: 'n4',
      from,
      to,
      cursor: 'event/2',
    })
    await getCurrentAlerts({ deviceId: 'n4', status: 'acknowledged', page: 2, pageSize: 100 })
    const body = {
      command_id: '550e8400-e29b-41d4-a716-446655440000',
      event_ts: to,
      note: 'Checked on site',
    }
    await acknowledgeAlert('alert/1', body)
    await resolveAlert('alert/1', body)
    await getEdaSummary({ deviceId: 'n2', from, to, bucket: '15m' })
    await getEdaDistributions({ deviceId: 'n2', from, to, field: 'score', bins: 5 })
    await getEdaCorrelation({
      deviceId: 'n2',
      from,
      to,
      xField: 'temperature_c',
      yField: 'score',
      maxPoints: 100,
      cursor: 'point/2',
    })
    await getModelEvaluations({ page: 2, pageSize: 50 })
    await getModelEvaluation('model/v1')
    await getSystemStatus()
    await getLiveness()
    await getReadiness()

    expect(fetchMock).toHaveBeenCalledTimes(15)
    expect(fetchMock.mock.calls.map(([path]) => String(path))).toEqual(Object.keys(responsesByPath))
    const acknowledgementInit = fetchMock.mock.calls[5]?.[1]
    expect(acknowledgementInit).toMatchObject({
      method: 'POST',
      body: JSON.stringify(body),
    })
    expect(new Headers(acknowledgementInit?.headers).get('content-type')).toBe('application/json')
  })

  it('rejects invalid query input before transport', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    await expect(
      getTelemetryHistory({ deviceId: 'n1', from: to, to: from }),
    ).rejects.toBeInstanceOf(z.ZodError)
    await expect(
      getEdaDistributions({ deviceId: 'n1', from, to, field: 'score', bins: 101 }),
    ).rejects.toBeInstanceOf(z.ZodError)
    await expect(
      getEdaCorrelation({
        from,
        to,
        xField: 'score',
        yField: 'score',
        maxPoints: 99,
      }),
    ).rejects.toBeInstanceOf(z.ZodError)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('sends a fully caller-supplied lifecycle body without generating identity fields', async () => {
    const body = {
      command_id: '550e8400-e29b-41d4-a716-446655440000',
      event_ts: to,
      note: 'same body',
    }
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        ...responsesByPath['/api/alerts/alert%2F1/acknowledge'],
        alert_id: 'alert-1',
        event: {
          event_id: 'event-1',
          alert_id: 'alert-1',
          event_ts: to,
          event_type: 'acknowledged',
          device_id: 'n4',
          actor: 'operator',
          note: null,
          inference_result_window_start_ts: null,
          inference_result_window_end_ts: null,
          inference_model_version: null,
        },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await acknowledgeAlert('alert-1', body)

    expect(fetchMock).toHaveBeenCalledOnce()
    expect(fetchMock.mock.calls[0]?.[1]?.body).toBe(JSON.stringify(body))
  })

  it('rejects telemetry responses beyond the requested limit', async () => {
    const point = {
      ts: from,
      temperature_c: 25,
      relative_humidity_pct: 70,
      sample_count: 1,
      gap_before: false,
    }
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({
          request_id: 'req-history-limit',
          device_id: 'n1',
          from,
          to,
          bucket: 'raw',
          points: [point, { ...point, ts: to }],
          next_cursor: null,
          returned_count: 2,
        }),
      ),
    )

    await expect(
      getTelemetryHistory({ deviceId: 'n1', from, to, limit: 1 }),
    ).rejects.toMatchObject({ kind: 'schema', requestId: 'req-history-limit' })
  })

  it('rejects bucketed inference responses above 2000 points', async () => {
    const point = {
      window_start_ts: from,
      window_end_ts: to,
      score: 0.2,
      threshold: 0.8,
      is_anomaly: false,
      model_version: 'model-v1',
      model_hash: 'model-hash',
      preprocessing_hash: 'preprocessing-hash',
      threshold_hash: 'threshold-hash',
    }
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({
          request_id: 'req-inference-limit',
          device_id: 'n1',
          model_version: 'model-v1',
          points: Array.from({ length: 2_001 }, () => point),
          next_cursor: null,
          returned_count: 2_001,
        }),
      ),
    )

    await expect(
      getInferenceResults({ deviceId: 'n1', from, to, bucket: '1m', limit: 2_000 }),
    ).rejects.toMatchObject({ kind: 'schema', requestId: 'req-inference-limit' })
  })

  it('rejects alert-event responses beyond the requested limit', async () => {
    const event = {
      event_id: 'event-1',
      alert_id: 'alert-1',
      event_ts: to,
      event_type: 'detected',
      device_id: 'n1',
      actor: 'system',
      note: null,
      inference_result_window_start_ts: from,
      inference_result_window_end_ts: to,
      inference_model_version: 'model-v1',
    }
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({
          request_id: 'req-event-limit',
          events: [event, { ...event, event_id: 'event-2' }],
          next_cursor: null,
          returned_count: 2,
        }),
      ),
    )

    await expect(getAlertEvents({ limit: 1 })).rejects.toMatchObject({
      kind: 'schema',
      requestId: 'req-event-limit',
    })
  })

  it('rejects EDA bins and points beyond caller-requested bounds', async () => {
    const histogramFetch = vi.fn().mockResolvedValue(
      jsonResponse({
        request_id: 'req-bin-limit',
        field: 'score',
        sample_count: 6,
        summary: { min: 0, max: 1, mean: 0.5, median: 0.5, p05: 0.1, p95: 0.9 },
        bins: Array.from({ length: 6 }, (_, index) => ({
          start: index,
          end: index + 1,
          count: 1,
        })),
      }),
    )
    vi.stubGlobal('fetch', histogramFetch)
    await expect(
      getEdaDistributions({ from, to, field: 'score', bins: 5 }),
    ).rejects.toMatchObject({ kind: 'schema', requestId: 'req-bin-limit' })

    const correlationPoint = {
      ts: from,
      device_id: 'n1',
      x: 25,
      y: 70,
      is_candidate_outlier: false,
    }
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({
          request_id: 'req-point-limit',
          x_field: 'temperature_c',
          y_field: 'relative_humidity_pct',
          sample_count: 101,
          correlation: 0.5,
          points: Array.from({ length: 101 }, () => correlationPoint),
          next_cursor: null,
        }),
      ),
    )
    await expect(
      getEdaCorrelation({ from, to, maxPoints: 100 }),
    ).rejects.toMatchObject({ kind: 'schema', requestId: 'req-point-limit' })
  })
})

describe('requestJson', () => {
  it('preserves successful response request_id values', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ request_id: 'req-success', value: 1 })),
    )
    await expect(
      requestJson('/api/value', z.strictObject({ request_id: z.string(), value: z.number() })),
    ).resolves.toEqual({ request_id: 'req-success', value: 1 })
  })

  it('rejects malformed success data as a schema error with its raw request id', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({ request_id: 'req-schema', sensors: 'wrong' }),
      ),
    )
    await expect(
      requestJson(
        '/api/telemetry/latest',
        z.strictObject({ request_id: z.string(), sensors: z.array(z.string()) }),
      ),
    ).rejects.toMatchObject({ kind: 'schema', requestId: 'req-schema' })
  })

  it('retains valid Problem Details from unsuccessful responses', async () => {
    const problem = {
      type: 'https://example.invalid/problems/conflict',
      title: 'Lifecycle conflict',
      status: 409,
      detail: 'Active alerts must be acknowledged before resolution',
      instance: '/api/alerts/alert-1/resolve',
      request_id: 'req-conflict',
      errors: { status: ['must be acknowledged'] },
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(problem, 409)))

    await expect(requestJson('/api/alerts/alert-1/resolve', z.never())).rejects.toMatchObject({
      kind: 'problem',
      status: 409,
      requestId: 'req-conflict',
      problem,
    })
  })

  it('classifies non-JSON HTTP failures without swallowing the status', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('gateway failed', { status: 502 })))

    await expect(requestJson('/api/system/status', z.never())).rejects.toMatchObject({
      kind: 'problem',
      status: 502,
      message: 'HTTP 502',
    })
  })

  it('classifies network failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(requestJson('/api/system/status', z.never())).rejects.toMatchObject({
      kind: 'network',
      message: 'Failed to fetch',
    })
  })

  it('times out after the default 8000 ms', async () => {
    vi.useFakeTimers()
    vi.stubGlobal(
      'fetch',
      vi.fn((_input: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => reject(init.signal?.reason), { once: true })
        }),
      ),
    )

    const request = requestJson('/api/system/status', z.never())
    const assertion = expect(request).rejects.toMatchObject({
      kind: 'timeout',
      message: 'Request timed out after 8000 ms',
    })
    await vi.advanceTimersByTimeAsync(8_000)
    await assertion
  })

  it('propagates caller cancellation instead of reclassifying it', async () => {
    const controller = new AbortController()
    const reason = new DOMException('Query replaced', 'AbortError')
    vi.stubGlobal(
      'fetch',
      vi.fn((_input: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => reject(init.signal?.reason), { once: true })
        }),
      ),
    )

    const request = requestJson('/api/system/status', z.never(), { signal: controller.signal })
    const assertion = expect(request).rejects.toBe(reason)
    controller.abort(reason)
    await assertion
  })

  it('does not convert ApiError instances into network errors', async () => {
    const error = new ApiError('schema', 'bad schema', undefined, 'req-1')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(error))
    await expect(requestJson('/api/value', z.never())).rejects.toBe(error)
  })
})

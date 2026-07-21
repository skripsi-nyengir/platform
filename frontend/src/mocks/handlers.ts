import { delay, http, HttpResponse, type HttpHandler } from 'msw'
import type {
  AcknowledgeAlertResponse,
  AlertEvent,
  CurrentAlert,
  CurrentAlertsResponse,
  ResolveAlertResponse,
} from '../contracts/alerts'
import { AlertEventsQuerySchema, CurrentAlertsQuerySchema } from '../contracts/alerts'
import {
  AlertCommandRequestSchema,
  SensorIdSchema,
  sensorIds,
  type ProblemDetails,
} from '../contracts/common'
import {
  EdaCorrelationQuerySchema,
  EdaDistributionQuerySchema,
  EdaSummaryQuerySchema,
  type CorrelationPoint,
  type EdaCorrelationResponse,
  type EdaDistributionResponse,
  type EdaField,
  type EdaSummaryResponse,
  type HistogramBin,
} from '../contracts/eda'
import { InferenceQuerySchema, type InferenceResponse } from '../contracts/inference'
import {
  ModelEvaluationsQuerySchema,
  type ModelEvaluationsResponse,
} from '../contracts/modelEvaluation'
import {
  TelemetryHistoryQuerySchema,
  type TelemetryHistoryResponse,
} from '../contracts/telemetry'
import { activeDetectedAlert } from './fixtures/alerts'
import {
  distributionSummaries,
  edaCorrelationPoints,
  edaMissingness,
  edaSensorComparisons,
} from './fixtures/eda'
import {
  activeAnomalyInferencePoints,
  fixtureModelVersion,
  normalInferencePoints,
} from './fixtures/inference'
import {
  modelEvaluationDetails,
  modelEvaluationSummaries,
} from './fixtures/modelEvaluations'
import {
  livenessResponse,
  readinessResponse,
  systemStatus,
} from './fixtures/systemHealth'
import {
  dataGapTelemetryHistoryPoints,
  fixtureGeneratedAt,
  latestTelemetrySensors,
  offlineTelemetrySensor,
  staleTelemetrySensor,
  telemetryHistoryPoints,
} from './fixtures/telemetry'
import type { MockApiState } from './state'

function problem(
  status: number,
  request_id: string,
  title: string,
  detail: string,
  instance: string,
) {
  const body = {
    type: `https://example.invalid/problems/${request_id}`,
    title,
    status,
    detail,
    instance,
    request_id,
  } satisfies ProblemDetails
  return HttpResponse.json(body, { status })
}

function queryValue(url: URL, key: string): string | undefined {
  return url.searchParams.get(key) ?? undefined
}

function queryNumber(url: URL, key: string): number | undefined {
  const value = queryValue(url, key)
  return value === undefined ? undefined : Number(value)
}

function invalidQuery(request: Request) {
  return problem(
    422,
    'req_invalid_query',
    'Invalid query',
    'Query parameters failed validation',
    new URL(request.url).pathname,
  )
}

function cursorOffset(url: URL, prefix: string): number {
  const cursor = url.searchParams.get('cursor')
  if (cursor === null) return 0
  const [kind, rawOffset, extra] = cursor.split(':')
  const offset = Number(rawOffset)
  return kind === prefix && extra === undefined && Number.isInteger(offset) && offset >= 0
    ? offset
    : 0
}

function nextCursor(prefix: string, offset: number, returned: number, total: number): string | null {
  const nextOffset = offset + returned
  return nextOffset < total ? `${prefix}:${nextOffset}` : null
}

function pathParam(value: string | readonly string[] | undefined): string {
  return String(value)
}

function currentAlert(state: MockApiState): CurrentAlert | undefined {
  const latest = state.events.at(-1)
  if (latest === undefined) return undefined
  const permissions = {
    detected: { can_acknowledge: true, can_resolve: false },
    acknowledged: { can_acknowledge: false, can_resolve: true },
    resolved: { can_acknowledge: false, can_resolve: false },
  }[latest.event_type]
  return {
    ...activeDetectedAlert,
    status: latest.event_type,
    latest_event_ts: latest.event_ts,
    latest_event_id: latest.event_id,
    ...permissions,
  }
}

function edaValue(point: CorrelationPoint, field: EdaField): number {
  if (field === 'temperature_c') return point.x
  if (field === 'relative_humidity_pct') return point.y
  return point.score ?? 0
}

async function mutateAlert(
  request: Request,
  state: MockApiState,
  alertId: string,
  action: 'acknowledged' | 'resolved',
) {
  const parsed = AlertCommandRequestSchema.safeParse(await request.json())
  if (!parsed.success) {
    return problem(400, 'req_invalid_command', 'Invalid alert command', parsed.error.message, request.url)
  }
  const command = parsed.data
  const note = command.note ?? null
  const accepted = state.acceptedCommands.get(command.command_id)
  if (accepted !== undefined) {
    const identical =
      accepted.alert_id === alertId &&
      accepted.status === action &&
      accepted.event.event_ts === command.event_ts &&
      accepted.event.note === note
    if (!identical) {
      return problem(
        409,
        'req_command_conflict',
        'Command ID conflict',
        'The command ID was already accepted with a different alert, action, timestamp, or note',
        request.url,
      )
    }
    return HttpResponse.json({ ...accepted, idempotent_replay: true })
  }

  const alertEvents = state.events.filter((event) => event.alert_id === alertId)
  const latest = alertEvents.at(-1)
  if (latest === undefined) {
    return problem(404, 'req_alert_not_found', 'Alert not found', `Alert ${alertId} was not found`, request.url)
  }
  if (Date.parse(command.event_ts) <= Date.parse(latest.event_ts)) {
    return problem(
      409,
      'req_event_order_conflict',
      'Alert event order conflict',
      'event_ts must be later than the current alert event',
      request.url,
    )
  }
  if (action === 'resolved' && latest.event_type === 'detected') {
    return problem(
      409,
      'req_direct_resolve',
      'Lifecycle conflict',
      'Detected alerts must be acknowledged before resolution',
      request.url,
    )
  }
  if (action === 'acknowledged' && latest.event_type !== 'detected') {
    return problem(
      409,
      'req_acknowledge_conflict',
      'Lifecycle conflict',
      'Only detected alerts can be acknowledged',
      request.url,
    )
  }
  if (action === 'resolved' && latest.event_type !== 'acknowledged') {
    return problem(
      409,
      'req_resolve_conflict',
      'Lifecycle conflict',
      'Only acknowledged alerts can be resolved',
      request.url,
    )
  }

  const detected = alertEvents[0]
  const event = Object.freeze({
    event_id: action === 'acknowledged' ? 'event_n4_ack_001' : 'event_n4_resolve_001',
    alert_id: alertId,
    event_ts: command.event_ts,
    event_type: action,
    device_id: latest.device_id,
    actor: 'operator',
    note,
    inference_result_window_start_ts: detected?.inference_result_window_start_ts ?? null,
    inference_result_window_end_ts: detected?.inference_result_window_end_ts ?? null,
    inference_model_version: detected?.inference_model_version ?? null,
  } satisfies AlertEvent)
  state.events = [...state.events, event]

  if (action === 'acknowledged') {
    const response = Object.freeze({
      request_id: 'req_acknowledge',
      alert_id: alertId,
      status: 'acknowledged',
      event,
      idempotent_replay: false,
    } satisfies AcknowledgeAlertResponse)
    state.acceptedCommands.set(command.command_id, response)
    return HttpResponse.json(response)
  }

  const response = Object.freeze({
    request_id: 'req_resolve',
    alert_id: alertId,
    status: 'resolved',
    event,
    idempotent_replay: false,
  } satisfies ResolveAlertResponse)
  state.acceptedCommands.set(command.command_id, response)
  return HttpResponse.json(response)
}

export function createHandlers(state: MockApiState): HttpHandler[] {
  return [
    http.get('/api/telemetry/latest', ({ request }) => {
      const url = new URL(request.url)
      const deviceValue = queryValue(url, 'device_id')
      const parsedDevice = deviceValue === undefined ? undefined : SensorIdSchema.safeParse(deviceValue)
      if (parsedDevice !== undefined && !parsedDevice.success) return invalidQuery(request)
      const deviceId = parsedDevice?.data
      let sensors = latestTelemetrySensors.map((sensor) => ({ ...sensor }))
      if (state.scenario === 'stale') {
        sensors = sensors.map((sensor) =>
          sensor.device_id === staleTelemetrySensor.device_id ? { ...staleTelemetrySensor } : sensor,
        )
      }
      if (state.scenario === 'offline') {
        sensors = sensors.map((sensor) =>
          sensor.device_id === offlineTelemetrySensor.device_id ? { ...offlineTelemetrySensor } : sensor,
        )
      }
      if (state.scenario === 'empty' && deviceId === 'n6') sensors = []
      else if (deviceId !== undefined) sensors = sensors.filter((sensor) => sensor.device_id === deviceId)
      return HttpResponse.json({
        request_id: 'req_telemetry_latest',
        generated_at: fixtureGeneratedAt,
        sensors,
      })
    }),

    http.get('/api/telemetry/history', ({ request }) => {
      const url = new URL(request.url)
      const parsed = TelemetryHistoryQuerySchema.safeParse({
        deviceId: queryValue(url, 'device_id'),
        from: queryValue(url, 'from'),
        to: queryValue(url, 'to'),
        bucket: queryValue(url, 'bucket'),
        limit: queryNumber(url, 'limit'),
        cursor: queryValue(url, 'cursor'),
      })
      if (!parsed.success) return invalidQuery(request)
      const { deviceId, from, to, bucket, limit } = parsed.data
      const offset = cursorOffset(url, 'telemetry')
      const source =
        state.scenario === 'empty' && deviceId === 'n6'
          ? []
          : state.scenario === 'data-gap' && deviceId === 'n5'
            ? dataGapTelemetryHistoryPoints
            : telemetryHistoryPoints
      const bounded = source
        .filter((point) => Date.parse(point.ts) >= Date.parse(from) && Date.parse(point.ts) < Date.parse(to))
        .map((point) => ({ ...point }))
      const points = bounded.slice(offset, offset + limit)
      const body = {
        request_id: 'req_telemetry_history',
        device_id: deviceId,
        from,
        to,
        bucket,
        points,
        next_cursor: nextCursor('telemetry', offset, points.length, bounded.length),
        returned_count: points.length,
      } satisfies TelemetryHistoryResponse
      return HttpResponse.json(body)
    }),

    http.get('/api/inference-results', ({ request }) => {
      const url = new URL(request.url)
      const parsed = InferenceQuerySchema.safeParse({
        deviceId: queryValue(url, 'device_id'),
        from: queryValue(url, 'from'),
        to: queryValue(url, 'to'),
        bucket: queryValue(url, 'bucket'),
        limit: queryNumber(url, 'limit'),
        cursor: queryValue(url, 'cursor'),
        modelVersion: queryValue(url, 'model_version'),
      })
      if (!parsed.success) return invalidQuery(request)
      const { deviceId, from, to, limit } = parsed.data
      const offset = cursorOffset(url, 'inference')
      const modelVersion = parsed.data.modelVersion ?? fixtureModelVersion
      const source =
        state.scenario === 'empty' && deviceId === 'n6'
          ? []
          : state.scenario === 'active-anomaly' && deviceId === 'n4'
            ? activeAnomalyInferencePoints
            : normalInferencePoints
      const bounded = source
        .filter(
          (point) =>
            Date.parse(point.window_start_ts) >= Date.parse(from) &&
            Date.parse(point.window_end_ts) <= Date.parse(to),
        )
        .map((point) => ({
          ...point,
          model_version: modelVersion,
          model_hash: `sha256:${modelVersion}`,
        }))
      const points = bounded.slice(offset, offset + limit)
      const body = {
        request_id: 'req_inference_results',
        device_id: deviceId,
        model_version: modelVersion,
        points,
        next_cursor: nextCursor('inference', offset, points.length, bounded.length),
        returned_count: points.length,
      } satisfies InferenceResponse
      return HttpResponse.json(body)
    }),

    http.get('/api/alert-events', ({ request }) => {
      const url = new URL(request.url)
      const parsed = AlertEventsQuerySchema.safeParse({
        alertId: queryValue(url, 'alert_id'),
        deviceId: queryValue(url, 'device_id'),
        from: queryValue(url, 'from'),
        to: queryValue(url, 'to'),
        limit: queryNumber(url, 'limit'),
        cursor: queryValue(url, 'cursor'),
      })
      if (!parsed.success) return invalidQuery(request)
      const { alertId, deviceId, from, to, limit } = parsed.data
      const offset = cursorOffset(url, 'alert-events')
      const filtered = state.events
        .filter((event) => alertId === undefined || event.alert_id === alertId)
        .filter((event) => deviceId === undefined || event.device_id === deviceId)
        .filter((event) => from === undefined || Date.parse(event.event_ts) >= Date.parse(from))
        .filter((event) => to === undefined || Date.parse(event.event_ts) < Date.parse(to))
        .toSorted((left, right) =>
          left.event_ts === right.event_ts
            ? left.event_id.localeCompare(right.event_id)
            : left.event_ts.localeCompare(right.event_ts),
        )
      const events = filtered.slice(offset, offset + limit).map((event) => ({ ...event }))
      return HttpResponse.json({
        request_id: 'req_alert_events',
        events,
        next_cursor: nextCursor('alert-events', offset, events.length, filtered.length),
        returned_count: events.length,
      })
    }),

    http.get('/api/alerts/current', ({ request }) => {
      const url = new URL(request.url)
      const parsed = CurrentAlertsQuerySchema.safeParse({
        deviceId: queryValue(url, 'device_id'),
        status: queryValue(url, 'status'),
        page: queryNumber(url, 'page'),
        pageSize: queryNumber(url, 'page_size'),
      })
      if (!parsed.success) return invalidQuery(request)
      const { deviceId, status, page, pageSize } = parsed.data
      const alert = currentAlert(state)
      const filtered = alert === undefined
        ? []
        : [alert]
            .filter((item) => deviceId === undefined || item.device_id === deviceId)
            .filter((item) => status === undefined || item.status === status)
      const start = (page - 1) * pageSize
      const body = {
        request_id: 'req_current_alerts',
        generated_at: fixtureGeneratedAt,
        items: filtered.slice(start, start + pageSize),
        page,
        page_size: pageSize,
        total: filtered.length,
      } satisfies CurrentAlertsResponse
      return HttpResponse.json(body)
    }),

    http.post('/api/alerts/:alertId/acknowledge', ({ request, params }) =>
      mutateAlert(request, state, pathParam(params.alertId), 'acknowledged'),
    ),

    http.post('/api/alerts/:alertId/resolve', ({ request, params }) =>
      mutateAlert(request, state, pathParam(params.alertId), 'resolved'),
    ),

    http.get('/api/eda/summary', ({ request }) => {
      const url = new URL(request.url)
      const parsed = EdaSummaryQuerySchema.safeParse({
        deviceId: queryValue(url, 'device_id'),
        from: queryValue(url, 'from'),
        to: queryValue(url, 'to'),
        bucket: queryValue(url, 'bucket'),
      })
      if (!parsed.success) return invalidQuery(request)
      const { deviceId, from, to, bucket } = parsed.data
      const empty = state.scenario === 'empty' && deviceId === 'n6'
      const gap = state.scenario === 'data-gap' && deviceId === 'n5'
      const comparisons = empty
        ? []
        : edaSensorComparisons
            .filter((comparison) => deviceId === undefined || comparison.device_id === deviceId)
            .map((comparison) => structuredClone(comparison))
      const expectedCount = empty ? 0 : comparisons.length * 6
      const observedCount = gap ? expectedCount - 1 : expectedCount
      const body = {
        request_id: 'req_eda_summary',
        scope: { device_ids: deviceId === undefined ? [...sensorIds] : [deviceId], from, to, bucket },
        coverage: {
          expected_count: expectedCount,
          observed_count: observedCount,
          coverage_pct: expectedCount === 0 ? 0 : Number(((observedCount / expectedCount) * 100).toFixed(2)),
          gap_count: gap ? 1 : 0,
        },
        missingness: empty
          ? []
          : gap
            ? [{ field: 'temperature_c', missing_count: 1, missing_pct: 16.67 }]
            : edaMissingness.map((item) => ({ ...item })),
        sensor_comparison: comparisons,
        candidate_outliers: [],
      } satisfies EdaSummaryResponse
      return HttpResponse.json(body)
    }),

    http.get('/api/eda/distributions', ({ request }) => {
      const url = new URL(request.url)
      const parsed = EdaDistributionQuerySchema.safeParse({
        deviceId: queryValue(url, 'device_id'),
        from: queryValue(url, 'from'),
        to: queryValue(url, 'to'),
        field: queryValue(url, 'field'),
        bins: queryNumber(url, 'bins'),
      })
      if (!parsed.success) return invalidQuery(request)
      const { deviceId, field, bins: requestedBins } = parsed.data
      const empty = state.scenario === 'empty' && deviceId === 'n6'
      const sampleCount = empty ? 0 : deviceId === undefined ? 36 : 6
      const summary = empty
        ? { min: 0, max: 0, mean: 0, median: 0, p05: 0, p95: 0 }
        : { ...distributionSummaries[field] }
      const width = empty ? 0 : (summary.max - summary.min) / requestedBins
      const bins: HistogramBin[] = empty
        ? []
        : Array.from({ length: requestedBins }, (_, index) => ({
            start: summary.min + width * index,
            end: summary.min + width * (index + 1),
            count: Math.floor(sampleCount / requestedBins) + (index < sampleCount % requestedBins ? 1 : 0),
          }))
      const body = {
        request_id: 'req_eda_distributions',
        field,
        sample_count: sampleCount,
        summary,
        bins,
      } satisfies EdaDistributionResponse
      return HttpResponse.json(body)
    }),

    http.get('/api/eda/correlation', ({ request }) => {
      const url = new URL(request.url)
      const parsed = EdaCorrelationQuerySchema.safeParse({
        deviceId: queryValue(url, 'device_id'),
        from: queryValue(url, 'from'),
        to: queryValue(url, 'to'),
        xField: queryValue(url, 'x_field'),
        yField: queryValue(url, 'y_field'),
        maxPoints: queryNumber(url, 'max_points'),
        cursor: queryValue(url, 'cursor'),
      })
      if (!parsed.success) return invalidQuery(request)
      const { deviceId, xField, yField, from, to, maxPoints: maximumPoints } = parsed.data
      const offset = cursorOffset(url, 'eda-correlation')
      const empty = state.scenario === 'empty' && deviceId === 'n6'
      const filtered = empty
        ? []
        : edaCorrelationPoints
            .filter((point) => deviceId === undefined || point.device_id === deviceId)
            .filter((point) => Date.parse(point.ts) >= Date.parse(from) && Date.parse(point.ts) < Date.parse(to))
      const bounded = filtered.map((point) => ({
        ...point,
        x: edaValue(point, xField),
        y: edaValue(point, yField),
      }))
      const points = bounded.slice(offset, offset + maximumPoints)
      const body = {
        request_id: 'req_eda_correlation',
        x_field: xField,
        y_field: yField,
        sample_count: bounded.length,
        correlation: bounded.length === 0 ? null : -0.72,
        points,
        next_cursor: nextCursor('eda-correlation', offset, points.length, bounded.length),
      } satisfies EdaCorrelationResponse
      return HttpResponse.json(body)
    }),

    http.get('/api/model-evaluations', ({ request }) => {
      const url = new URL(request.url)
      const parsed = ModelEvaluationsQuerySchema.safeParse({
        page: queryNumber(url, 'page'),
        pageSize: queryNumber(url, 'page_size'),
      })
      if (!parsed.success) return invalidQuery(request)
      const { page, pageSize } = parsed.data
      const start = (page - 1) * pageSize
      const body = {
        request_id: 'req_model_evaluations',
        items: modelEvaluationSummaries.slice(start, start + pageSize).map((item) => structuredClone(item)),
        page,
        page_size: pageSize,
        total: modelEvaluationSummaries.length,
      } satisfies ModelEvaluationsResponse
      return HttpResponse.json(body)
    }),

    http.get('/api/model-evaluations/:version', ({ params }) => {
      const version = pathParam(params.version)
      const detail = Object.values(modelEvaluationDetails).find((item) => item.version === version)
      return detail === undefined
        ? problem(
            404,
            'req_model_not_found',
            'Model evaluation not found',
            `Model evaluation ${version} was not found`,
            `/api/model-evaluations/${version}`,
          )
        : HttpResponse.json(structuredClone(detail))
    }),

    http.get('/api/system/status', async () => {
      if (state.scenario === 'timeout') await delay(8_100)
      if (state.scenario === 'server-error') {
        return HttpResponse.json(
          {
            type: 'https://example.invalid/problems/mock-service-unavailable',
            title: 'Mock service unavailable',
            status: 503,
            detail: 'The deterministic mock system status endpoint failed',
            instance: '/api/system/status',
            request_id: 'req_server_error',
          } satisfies ProblemDetails,
          { status: 503 },
        )
      }
      const telemetry =
        state.scenario === 'stale'
          ? { ...systemStatus.telemetry, fresh_sensor_count: 5, stale_sensor_count: 1 }
          : state.scenario === 'offline'
            ? { ...systemStatus.telemetry, fresh_sensor_count: 5, offline_sensor_count: 1 }
            : { ...systemStatus.telemetry }
      return HttpResponse.json({ ...systemStatus, telemetry })
    }),

    http.get('/health', () => HttpResponse.json(livenessResponse)),
    http.get('/ready', () => HttpResponse.json(readinessResponse)),
  ]
}

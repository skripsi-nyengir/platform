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
  compareHistoricalDateTimes,
  SensorIdSchema,
  publicDeviceId,
  simDeviceId,
  type ProblemDetails,
} from '../contracts/common'
import {
  EdaComputeRequestSchema,
  EdaPeriodListQuerySchema,
  EdaSectionNameSchema,
  type EdaJobResponse,
  type EdaRunResponse,
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
  edaCacheHitResponse,
  edaCanonicalRun,
  edaChangePointsNotEligibleSection,
  edaFailedJob,
  edaFailedSection,
  edaNotEligibleSection,
  edaPeriodListResponse,
  edaPublishedCustomRun,
  edaQueuedComputeResponse,
  edaQueuedCustomJob,
  edaReadyMonthlyRun,
  edaReadyWeeklyRun,
  edaRunningComputeResponse,
  edaRunningCustomJob,
  edaSectionsByName,
  edaSucceededJob,
  edaUncertaintyNotEligibleSection,
} from './fixtures/eda'
import {
  activeAnomalyInferenceBySensor,
  normalInferenceBySensor,
} from './fixtures/inference'
import {
  modelEvaluationDetails,
  modelEvaluationSummaries,
} from './fixtures/modelEvaluations'
import { modelRegistryResponse } from './fixtures/modelRegistry'
import { offlineEvaluationsResponse } from './fixtures/offlineEvaluations'
import {
  livenessResponse,
  readinessResponse,
  systemStatus,
} from './fixtures/systemHealth'
import {
  dailyTelemetryHistoryBySensor,
  dataGapTelemetryHistoryBySensor,
  latestTelemetrySensors,
  offlineTelemetrySensor,
  staleTelemetrySensor,
  telemetryHistoryBySensor,
} from './fixtures/telemetry'
import type { MockApiState } from './state'
import {
  ModelActivationRequestSchema,
  ReplayJobRequestSchema,
  type ModelActivationResponse,
  type ReplayJobResponse,
} from '../contracts/preview'
import {
  SetSimActiveModelRequestSchema,
  type SetSimActiveModelResponse,
} from '../contracts/simulation'
import type { LatestTelemetrySensor, TelemetryPoint } from '../contracts/telemetry'
import { modelsResponse, previewDevice, replayJob } from './fixtures/preview'
import {
  simulationInferencePoints,
  simulationInjectionEvents,
  simulationModelsResponse,
  simulationTelemetryPoints,
} from './fixtures/simulation'

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

function requestCount(state: MockApiState, key: string): number {
  const count = (state.edaRequestCounts.get(key) ?? 0) + 1
  state.edaRequestCounts.set(key, count)
  return count
}

function pathParam(value: string | readonly string[] | undefined): string {
  return String(value)
}

const scenarioDevice = {
  'active-anomaly': publicDeviceId,
  stale: publicDeviceId,
  offline: publicDeviceId,
  'data-gap': publicDeviceId,
  empty: publicDeviceId,
} as const

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
    latest_event_at: latest.event_at,
    latest_event_id: latest.event_id,
    ...permissions,
  }
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
    event_id:
      action === 'acknowledged' ? 'event_b02_ack_001' : 'event_b02_resolve_001',
    alert_id: alertId,
    event_at: action === 'acknowledged' ? '2026-06-01T00:01:00Z' : '2026-06-01T00:02:00Z',
    event_type: action,
    device_id: latest.device_id,
    actor: 'preview-session',
    note,
    accepted_at: action === 'acknowledged' ? '2026-06-01T00:01:00Z' : '2026-06-01T00:02:00Z',
    inference_model_version: detected?.inference_model_version ?? null,
    detection_basis: 'simulated_preview',
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
    http.get('/api/simulation/models', () =>
      HttpResponse.json(simulationModelsResponse(state.simActiveModelVersion)),
    ),

    http.post('/api/simulation/active-model', async ({ request }) => {
      const parsed = SetSimActiveModelRequestSchema.safeParse(await request.json())
      if (!parsed.success) {
        return problem(400, 'req_invalid_sim_model', 'Invalid model selection', parsed.error.message, request.url)
      }
      const exists = simulationModelsResponse(state.simActiveModelVersion).models.some(
        (model) => model.version === parsed.data.model_version,
      )
      if (!exists) {
        return problem(404, 'req_sim_model_not_found', 'Model not found', 'The artifact model was not found', request.url)
      }
      state.simActiveModelVersion = parsed.data.model_version
      const response = {
        request_id: 'req_simulation_active_model',
        device_id: simDeviceId,
        active_model_version: state.simActiveModelVersion,
      } satisfies SetSimActiveModelResponse
      return HttpResponse.json(response)
    }),

    http.get('/api/injection-events', ({ request }) => {
      const url = new URL(request.url)
      if (queryValue(url, 'device_id') !== simDeviceId) return invalidQuery(request)
      return HttpResponse.json({
        request_id: 'req_injection_events',
        device_id: simDeviceId,
        time_zone: 'Asia/Jakarta',
        events: simulationInjectionEvents.map((event) => ({ ...event })),
        returned_count: simulationInjectionEvents.length,
      })
    }),

    http.get('/api/devices', () => HttpResponse.json({
      request_id: 'req_devices',
      items: [structuredClone(previewDevice)],
    })),

    http.get('/api/models', ({ request }) => {
      const url = new URL(request.url)
      if (queryValue(url, 'device_id') !== publicDeviceId) return invalidQuery(request)
      return HttpResponse.json(modelsResponse(state.activeModelVersion))
    }),

    http.post('/api/model-activations', async ({ request }) => {
      const parsed = ModelActivationRequestSchema.safeParse(await request.json())
      if (!parsed.success) return invalidQuery(request)
      const prior = state.activeModelVersion
      state.activeModelVersion = parsed.data.model_version
      const response = {
        request_id: 'req_activation',
        activation: {
          activation_id: `activation-${parsed.data.command_id}`,
          command_id: parsed.data.command_id,
          device_id: publicDeviceId,
          prior_model_version: prior,
          model_version: parsed.data.model_version,
          changed: prior !== parsed.data.model_version,
          activated_at: '2026-07-24T08:00:00Z',
          actor: 'preview-session',
        },
        active_model_version: state.activeModelVersion,
        idempotent_request_replay: false,
      } satisfies ModelActivationResponse
      return HttpResponse.json(response)
    }),

    http.post('/api/replay-jobs', async ({ request }) => {
      const parsed = ReplayJobRequestSchema.safeParse(await request.json())
      if (!parsed.success) return invalidQuery(request)
      const existing = state.replayJobs.get(parsed.data.command_id)
      const modelVersion = parsed.data.device_id === simDeviceId
        ? state.simActiveModelVersion
        : state.activeModelVersion
      const job = existing ?? replayJob(
        `replay-${parsed.data.command_id}`,
        parsed.data.from,
        parsed.data.to,
        modelVersion,
        'running',
        parsed.data.device_id,
      )
      state.replayJobs.set(parsed.data.command_id, job)
      const response = {
        request_id: 'req_replay_create',
        job,
        idempotent_request_replay: existing !== undefined,
      } satisfies ReplayJobResponse
      return HttpResponse.json(response, { status: existing === undefined ? 202 : 200 })
    }),

    http.get('/api/replay-jobs/:jobId', ({ request, params }) => {
      const requestedId = pathParam(params.jobId)
      const existing = [...state.replayJobs.values()].find((job) => job.job_id === requestedId)
      if (existing === undefined) {
        return problem(404, 'req_replay_not_found', 'Replay not found', 'Replay job was not found', request.url)
      }
      const completed = { ...existing, ...replayJob(
        existing.job_id,
        existing.from,
        existing.to,
        existing.model_version,
        'succeeded',
        existing.device_id,
      ) }
      state.replayJobs.set(
        [...state.replayJobs.entries()].find(([, job]) => job.job_id === requestedId)?.[0] ?? requestedId,
        completed,
      )
      return HttpResponse.json({ request_id: 'req_replay_status', job: completed })
    }),

    http.get('/api/telemetry/latest', ({ request }) => {
      const url = new URL(request.url)
      const deviceValue = queryValue(url, 'device_id')
      const parsedDevice = deviceValue === undefined ? undefined : SensorIdSchema.safeParse(deviceValue)
      if (parsedDevice !== undefined && !parsedDevice.success) return invalidQuery(request)
      const deviceId = parsedDevice?.data
      let sensors: LatestTelemetrySensor[] = latestTelemetrySensors.map((sensor) => ({ ...sensor }))
       if (state.scenario === 'stale') {
         sensors = sensors.map((sensor) =>
           sensor.device_id === scenarioDevice.stale ? { ...staleTelemetrySensor } : sensor,
         )
       }
       if (state.scenario === 'offline') {
         sensors = sensors.map((sensor) =>
           sensor.device_id === scenarioDevice.offline ? { ...offlineTelemetrySensor } : sensor,
         )
       }
       if (state.scenario === 'empty' && deviceId === scenarioDevice.empty) sensors = []
      else if (deviceId !== undefined) sensors = sensors.filter((sensor) => sensor.device_id === deviceId)
      return HttpResponse.json({
        request_id: 'req_telemetry_latest',
        time_zone: 'Asia/Jakarta',
        generated_at: '2026-07-24T08:00:00Z',
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
       const source: readonly TelemetryPoint[] = deviceId === simDeviceId
         ? simulationTelemetryPoints
         : state.scenario === 'empty' && deviceId === scenarioDevice.empty
           ? []
           : state.scenario === 'data-gap'
             ? dataGapTelemetryHistoryBySensor[deviceId]
             : bucket === '1d'
               ? dailyTelemetryHistoryBySensor[deviceId]
               : telemetryHistoryBySensor[deviceId]
       const bounded = source
         .filter(
           (point) =>
             compareHistoricalDateTimes(point.ts, from) >= 0 &&
             compareHistoricalDateTimes(point.ts, to) < 0,
         )
        .map((point) => ({ ...point }))
      const points = bounded.slice(offset, offset + limit)
      const body = {
        request_id: 'req_telemetry_history',
        device_id: deviceId,
        time_zone: 'Asia/Jakarta',
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
       const modelVersion = deviceId === simDeviceId
         ? parsed.data.modelVersion ?? state.simActiveModelVersion
         : normalInferenceBySensor[deviceId][0].model_version
       const knownSimulationModel = simulationModelsResponse(state.simActiveModelVersion).models.some(
         (model) => model.version === modelVersion,
       )
       const source = deviceId === simDeviceId
         ? knownSimulationModel ? simulationInferencePoints(modelVersion) : []
         : state.scenario === 'empty' && deviceId === scenarioDevice.empty
           ? []
           : state.scenario === 'active-anomaly' && deviceId === scenarioDevice['active-anomaly']
             ? activeAnomalyInferenceBySensor[deviceId]
             : normalInferenceBySensor[deviceId]
       const modelFiltered = deviceId === simDeviceId ||
         parsed.data.modelVersion === undefined || parsed.data.modelVersion === modelVersion ? source : []
       const bounded = modelFiltered
         .filter(
           (point) =>
             compareHistoricalDateTimes(point.window_start_ts, from) >= 0 &&
             compareHistoricalDateTimes(point.window_end_ts, to) <= 0,
         )
         .map((point) => ({ ...point }))
      const points = bounded.slice(offset, offset + limit)
      const body = {
        request_id: 'req_inference_results',
        device_id: deviceId,
        time_zone: 'Asia/Jakarta',
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
      const { alertId, deviceId, limit } = parsed.data
      const offset = cursorOffset(url, 'alert-events')
      const filtered = state.events
        .filter((event) => alertId === undefined || event.alert_id === alertId)
        .filter((event) => deviceId === undefined || event.device_id === deviceId)
        .toSorted((left, right) =>
          left.event_at === right.event_at
            ? left.event_id.localeCompare(right.event_id)
            : left.event_at.localeCompare(right.event_at),
        )
      const events = filtered.slice(offset, offset + limit).map((event) => ({ ...event }))
      return HttpResponse.json({
        request_id: 'req_alert_events',
        time_zone: 'Asia/Jakarta',
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
        time_zone: 'Asia/Jakarta',
        generated_at: '2026-07-24T08:00:00Z',
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

    http.get('/api/eda/periods', ({ request }) => {
      const url = new URL(request.url)
      const parsed = EdaPeriodListQuerySchema.safeParse({
        period_kind: queryValue(url, 'period_kind'),
        cursor: queryValue(url, 'cursor') ?? null,
        limit: queryNumber(url, 'limit'),
      })
      if (!parsed.success) return invalidQuery(request)
      const count = requestCount(state, `period:${parsed.data.period_kind}`)
      if (state.scenario === 'eda-period-error' && count === 1) {
        return problem(
          503,
          `req-eda-period-${parsed.data.period_kind}`,
          'EDA period list unavailable',
          `Daftar ${parsed.data.period_kind} gagal dimuat untuk uji pemulihan.`,
          new URL(request.url).pathname,
        )
      }
      const available = state.scenario === 'eda-latest-fallback'
        ? parsed.data.period_kind === 'weekly' ? [edaReadyWeeklyRun] : []
        : parsed.data.period_kind === 'monthly' ? edaPeriodListResponse.items : []
      const offset = cursorOffset(url, 'eda-periods')
      const items = available.slice(offset, offset + parsed.data.limit)
      const body = {
        request_id: edaPeriodListResponse.request_id,
        period_kind: parsed.data.period_kind,
        items,
        next_cursor: nextCursor('eda-periods', offset, items.length, available.length),
        returned_count: items.length,
      }
      return HttpResponse.json(body)
    }),

    http.post('/api/eda/compute', async ({ request }) => {
      const parsed = EdaComputeRequestSchema.safeParse(await request.json())
      if (!parsed.success) return invalidQuery(request)
      const count = requestCount(state, 'compute')
      const cacheHit = parsed.data.from === edaCacheHitResponse.run.scope.from &&
        parsed.data.to === edaCacheHitResponse.run.scope.to
      if (state.scenario === 'eda-job-queued') {
        return HttpResponse.json(edaQueuedComputeResponse, { status: 202 })
      }
      if (state.scenario === 'eda-job-failed' && count > 1) {
        return HttpResponse.json(edaCacheHitResponse)
      }
      return HttpResponse.json(cacheHit ? edaCacheHitResponse : edaRunningComputeResponse, {
        status: cacheHit ? 200 : 202,
      })
    }),

    http.get('/api/eda/jobs/:jobId', ({ request, params }) => {
      const jobId = pathParam(params.jobId)
      const count = requestCount(state, `job:${jobId}`)
      if (state.scenario === 'eda-job-error' && count === 1) {
        return problem(
          503,
          'req-eda-job-status',
          'EDA job status unavailable',
          'Status pekerjaan EDA gagal dimuat untuk uji pemulihan.',
          new URL(request.url).pathname,
        )
      }
      const scenarioJob = state.scenario === 'eda-job-queued'
        ? { ...edaQueuedCustomJob, job_id: jobId }
        : state.scenario === 'eda-job-running'
          ? { ...edaRunningCustomJob, job_id: jobId }
          : state.scenario === 'eda-job-success' || state.scenario === 'eda-job-error'
            ? { ...edaSucceededJob, job_id: jobId }
            : state.scenario === 'eda-job-failed'
              ? { ...edaFailedJob, job_id: jobId }
              : undefined
      const job = scenarioJob ?? (jobId === edaRunningCustomJob.job_id
        ? edaRunningCustomJob
        : jobId === edaFailedJob.job_id
          ? edaFailedJob
          : jobId === edaSucceededJob.job_id
            ? edaSucceededJob
          : undefined)
      if (job === undefined) {
        return problem(404, 'req-eda-job-not-found', 'EDA job not found', 'Pekerjaan EDA tidak ditemukan.', request.url)
      }
      const body = {
        request_id: 'req-eda-job',
        job,
      } satisfies EdaJobResponse
      return HttpResponse.json(body)
    }),

    http.get('/api/eda/runs/:runId', ({ request, params }) => {
      const runId = pathParam(params.runId)
      const run = runId === edaReadyMonthlyRun.run_id
        ? edaReadyMonthlyRun
        : runId === edaReadyWeeklyRun.run_id
          ? edaReadyWeeklyRun
          : runId === edaCanonicalRun.run_id
            ? edaCanonicalRun
        : runId === edaCacheHitResponse.run.run_id
          ? edaCacheHitResponse.run
          : runId === edaPublishedCustomRun.run_id
            ? edaPublishedCustomRun
          : undefined
      if (run === undefined) {
        return problem(404, 'req-eda-run-not-found', 'EDA run not found', 'Hasil EDA tidak ditemukan.', request.url)
      }
      const body = { request_id: 'req-eda-run', run } satisfies EdaRunResponse
      return HttpResponse.json(body)
    }),

    http.get('/api/eda/runs/:runId/sections/:section', ({ request, params }) => {
      const runId = pathParam(params.runId)
      const knownRunIds = [
        edaReadyMonthlyRun.run_id,
        edaReadyWeeklyRun.run_id,
        edaCanonicalRun.run_id,
        edaCacheHitResponse.run.run_id,
        edaPublishedCustomRun.run_id,
      ]
      if (!knownRunIds.includes(runId)) {
        return problem(404, 'req-eda-run-not-found', 'EDA run not found', 'Hasil EDA tidak ditemukan.', request.url)
      }
      const parsedSection = EdaSectionNameSchema.safeParse(pathParam(params.section))
      if (!parsedSection.success) return invalidQuery(request)
      const count = requestCount(state, `section:${parsedSection.data}`)
      const failsOnce = state.scenario === 'eda-section-error' && parsedSection.data === 'uncertainty'
      const failsMultipleOnce = state.scenario === 'eda-multiple-section-error' &&
        (parsedSection.data === 'relationships' || parsedSection.data === 'stationarity')
      if ((failsOnce || failsMultipleOnce) && count === 1) {
        return problem(
          503,
          `req-eda-section-${parsedSection.data}`,
          'EDA section unavailable',
          `Bagian ${parsedSection.data} gagal dimuat untuk uji isolasi.`,
          new URL(request.url).pathname,
        )
      }
      if (state.scenario === 'eda-custom-not-eligible') {
        if (parsedSection.data === 'change_points') {
          return HttpResponse.json({ ...edaChangePointsNotEligibleSection, run_id: runId })
        }
        if (parsedSection.data === 'uncertainty') {
          return HttpResponse.json({ ...edaUncertaintyNotEligibleSection, run_id: runId })
        }
      }
      if (
        state.scenario === 'eda-canonical' ||
        state.scenario === 'eda-custom-not-eligible' ||
        state.scenario === 'eda-section-error' ||
        state.scenario === 'eda-multiple-section-error'
      ) {
        const completeSection = edaSectionsByName.get(parsedSection.data)
        if (completeSection !== undefined) {
          return HttpResponse.json({ ...completeSection, run_id: runId })
        }
      }
      if (parsedSection.data === edaNotEligibleSection.section) {
        return HttpResponse.json({ ...edaNotEligibleSection, run_id: runId })
      }
      if (parsedSection.data === edaFailedSection.section) {
        return HttpResponse.json({ ...edaFailedSection, run_id: runId })
      }
      const section = edaSectionsByName.get(parsedSection.data)
      if (section === undefined) {
        return problem(404, 'req-eda-section-not-found', 'EDA section not found', 'Bagian EDA tidak ditemukan.', request.url)
      }
      return HttpResponse.json({ ...section, run_id: runId })
    }),

    http.get('/api/model-registry', () => HttpResponse.json(structuredClone(modelRegistryResponse))),

    http.get('/api/offline-evaluations', () =>
      HttpResponse.json(structuredClone(offlineEvaluationsResponse)),
    ),

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
           ? {
               ...systemStatus.telemetry,
               fresh_sensor_count: 0,
               stale_sensor_count: 1,
               offline_sensor_count: 0,
             }
           : state.scenario === 'offline'
             ? {
                 ...systemStatus.telemetry,
                 fresh_sensor_count: 0,
                 stale_sensor_count: 0,
                 offline_sensor_count: 1,
               }
             : { ...systemStatus.telemetry }
      return HttpResponse.json({ ...systemStatus, telemetry })
    }),

    http.get('/health', () => HttpResponse.json(livenessResponse)),
    http.get('/ready', () => HttpResponse.json(readinessResponse)),
  ]
}

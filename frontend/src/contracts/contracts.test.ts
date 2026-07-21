import { describe, expect, it } from 'vitest'
import {
  AlertCommandRequestSchema,
  BucketSchema,
  ProblemDetailsSchema,
  Rfc3339Schema,
  SensorIdSchema,
} from './common'
import {
  LatestTelemetryResponseSchema,
  TelemetryPointSchema,
  TelemetryHistoryQuerySchema,
  TelemetryHistoryResponseSchema,
} from './telemetry'
import {
  InferencePointSchema,
  InferenceQuerySchema,
  InferenceResponseSchema,
} from './inference'
import {
  AcknowledgeAlertResponseSchema,
  AlertEventsQuerySchema,
  AlertEventsResponseSchema,
  CurrentAlertsQuerySchema,
  CurrentAlertsResponseSchema,
  ResolveAlertResponseSchema,
} from './alerts'
import {
  CorrelationPointSchema,
  DistributionSummarySchema,
  EdaCorrelationQuerySchema,
  EdaCorrelationResponseSchema,
  EdaDistributionQuerySchema,
  EdaDistributionResponseSchema,
  EdaSummaryQuerySchema,
  EdaSummaryResponseSchema,
  HistogramBinSchema,
} from './eda'
import {
  ModelEvaluationDetailSchema,
  ModelEvaluationsQuerySchema,
  ModelEvaluationsResponseSchema,
  PrecisionRecallCurveSchema,
  PrecisionRecallPointSchema,
  RocCurveSchema,
  RocPointSchema,
} from './modelEvaluation'
import {
  LivenessResponseSchema,
  ReadinessResponseSchema,
  SystemStatusResponseSchema,
} from './systemHealth'

const from = '2026-07-19T09:00:00Z'
const to = '2026-07-19T10:00:00+00:00'

const alertEvent = {
  event_id: 'event-1',
  alert_id: 'alert-1',
  event_ts: to,
  event_type: 'acknowledged',
  device_id: 'n4',
  actor: 'operator',
  note: 'Checked on site',
  inference_result_window_start_ts: from,
  inference_result_window_end_ts: to,
  inference_model_version: 'model-v1',
} as const

const telemetryPoint = {
  ts: from,
  temperature_c: 25.1,
  relative_humidity_pct: 70.2,
  sample_count: 60,
  gap_before: false,
} as const

const inferencePoint = {
  window_start_ts: from,
  window_end_ts: to,
  score: 0.2,
  threshold: 0.8,
  is_anomaly: false,
  model_version: 'model-v1',
  model_hash: 'sha256:model',
  preprocessing_hash: 'sha256:preprocessing',
  threshold_hash: 'sha256:threshold',
} as const

const evaluationDetail = {
  request_id: 'req-model-detail',
  version: 'model-v1',
  created_at: to,
  evaluation_period: '2026-07-01 to 2026-07-18',
  model_hash: 'sha256:model',
  preprocessing_hash: 'sha256:preprocessing',
  threshold_hash: 'sha256:threshold',
  has_labeled_ground_truth: true,
  available_metrics: ['mae', 'roc', 'confusion_matrix', 'precision_recall'],
  metrics: { mae: 0.12 },
  confusion_matrix: {
    labels: ['normal', 'anomaly'],
    matrix: [
      [80, 4],
      [3, 13],
    ],
  },
  roc: { auc: 0.98, points: [{ fpr: 0, tpr: 0 }, { fpr: 1, tpr: 1 }] },
  precision_recall: {
    average_precision: 0.94,
    points: [{ recall: 0, precision: 1 }, { recall: 1, precision: 0.5 }],
  },
  notes: 'Held-out labeled artifact',
} as const

describe('shared contracts', () => {
  it('accepts only the fixed sensors, buckets, and offset-aware timestamps', () => {
    expect(SensorIdSchema.parse('n6')).toBe('n6')
    expect(BucketSchema.parse('15m')).toBe('15m')
    expect(Rfc3339Schema.parse('2026-07-19T10:00:00+07:00')).toBe(
      '2026-07-19T10:00:00+07:00',
    )
    expect(SensorIdSchema.safeParse('n7').success).toBe(false)
    expect(Rfc3339Schema.safeParse('2026-07-19T10:00:00').success).toBe(false)
  })

  it('strictly validates Problem Details', () => {
    const problem = {
      type: 'https://example.invalid/problems/invalid-time-range',
      title: 'Invalid time range',
      status: 422,
      detail: 'from must be earlier than to',
      instance: '/api/telemetry/history',
      request_id: 'req-problem',
      errors: { from: ['must be earlier than to'] },
    }
    expect(ProblemDetailsSchema.parse(problem)).toEqual(problem)
    expect(ProblemDetailsSchema.safeParse({ ...problem, extra: true }).success).toBe(false)
  })

  it('treats command_id as caller-supplied opaque text', () => {
    expect(
      AlertCommandRequestSchema.parse({ command_id: 'operator-command-1', event_ts: to }),
    ).toEqual({ command_id: 'operator-command-1', event_ts: to })
  })
})

describe('successful endpoint responses', () => {
  it('parses latest telemetry with independent freshness and availability', () => {
    const response = {
      request_id: 'req-latest',
      generated_at: to,
      sensors: [
        {
          device_id: 'n1',
          ts: from,
          temperature_c: 26.5,
          relative_humidity_pct: 71,
          freshness: 'stale',
          age_seconds: 3_600,
          availability: 'online',
        },
        {
          device_id: 'n2',
          ts: from,
          temperature_c: null,
          relative_humidity_pct: null,
          freshness: 'unknown',
          age_seconds: 3_600,
          availability: 'offline',
        },
      ],
    }
    expect(LatestTelemetryResponseSchema.parse(response)).toEqual(response)
  })

  it('parses bounded telemetry and inference histories', () => {
    expect(
      TelemetryHistoryResponseSchema.parse({
        request_id: 'req-history',
        device_id: 'n1',
        from,
        to,
        bucket: '1m',
        points: [telemetryPoint],
        next_cursor: null,
        returned_count: 1,
      }),
    ).toMatchObject({ request_id: 'req-history', returned_count: 1 })

    expect(
      InferenceResponseSchema.parse({
        request_id: 'req-inference',
        device_id: 'n1',
        model_version: 'model-v1',
        points: [inferencePoint],
        next_cursor: 'cursor-2',
        returned_count: 1,
      }),
    ).toMatchObject({ request_id: 'req-inference', returned_count: 1 })
  })

  it('parses alert event, current-state, acknowledge, and resolve responses', () => {
    expect(
      AlertEventsResponseSchema.parse({
        request_id: 'req-events',
        events: [alertEvent],
        next_cursor: null,
        returned_count: 1,
      }),
    ).toMatchObject({ returned_count: 1 })

    expect(
      CurrentAlertsResponseSchema.parse({
        request_id: 'req-current',
        generated_at: to,
        items: [
          {
            alert_id: 'alert-1',
            device_id: 'n4',
            status: 'detected',
            detected_at: from,
            latest_event_ts: to,
            latest_event_id: 'event-0',
            score: 0.92,
            threshold: 0.8,
            model_version: 'model-v1',
            can_acknowledge: true,
            can_resolve: false,
          },
        ],
        page: 1,
        page_size: 25,
        total: 1,
      }),
    ).toMatchObject({ total: 1 })

    expect(
      AcknowledgeAlertResponseSchema.parse({
        request_id: 'req-ack',
        alert_id: 'alert-1',
        status: 'acknowledged',
        event: alertEvent,
        idempotent_replay: false,
      }),
    ).toMatchObject({ status: 'acknowledged' })

    expect(
      ResolveAlertResponseSchema.parse({
        request_id: 'req-resolve',
        alert_id: 'alert-1',
        status: 'resolved',
        event: { ...alertEvent, event_id: 'event-2', event_type: 'resolved' },
        idempotent_replay: true,
      }),
    ).toMatchObject({ status: 'resolved', idempotent_replay: true })
  })

  it('parses EDA summary, distributions, and correlation responses', () => {
    expect(
      EdaSummaryResponseSchema.parse({
        request_id: 'req-eda-summary',
        scope: { device_ids: ['n1', 'n2'], from, to, bucket: '15m' },
        coverage: {
          expected_count: 120,
          observed_count: 118,
          coverage_pct: 98.33,
          gap_count: 1,
        },
        missingness: [
          { field: 'temperature_c', missing_count: 2, missing_pct: 1.67 },
        ],
        sensor_comparison: [
          {
            device_id: 'n1',
            sample_count: 59,
            coverage_pct: 98.33,
            temperature_c: { mean: 25, p05: 23, p95: 27 },
            relative_humidity_pct: { mean: 70, p05: 65, p95: 75 },
          },
        ],
        candidate_outliers: [
          {
            device_id: 'n2',
            start_ts: from,
            end_ts: to,
            reason: 'score threshold candidate',
            score: 0.91,
          },
        ],
      }),
    ).toMatchObject({ request_id: 'req-eda-summary' })

    expect(
      EdaDistributionResponseSchema.parse({
        request_id: 'req-eda-distribution',
        field: 'temperature_c',
        sample_count: 118,
        summary: { min: 20, max: 30, mean: 25, median: 25, p05: 21, p95: 29 },
        bins: [{ start: 20, end: 22, count: 10 }],
      }),
    ).toMatchObject({ field: 'temperature_c' })

    expect(
      EdaCorrelationResponseSchema.parse({
        request_id: 'req-eda-correlation',
        x_field: 'temperature_c',
        y_field: 'relative_humidity_pct',
        sample_count: 1,
        correlation: -0.7,
        points: [
          {
            ts: from,
            device_id: 'n1',
            x: 25,
            y: 70,
            score: 0.2,
            is_candidate_outlier: false,
          },
        ],
        next_cursor: null,
      }),
    ).toMatchObject({ correlation: -0.7 })
  })

  it('allows correlation sample_count to describe a population larger than returned points', () => {
    expect(
      EdaCorrelationResponseSchema.parse({
        request_id: 'req-eda-correlation-population',
        x_field: 'temperature_c',
        y_field: 'relative_humidity_pct',
        sample_count: 5_001,
        correlation: 0.4,
        points: [
          {
            ts: from,
            device_id: 'n1',
            x: 25,
            y: 70,
            is_candidate_outlier: false,
          },
        ],
        next_cursor: null,
      }),
    ).toMatchObject({ sample_count: 5_001, points: [{ device_id: 'n1' }] })
  })

  it('parses model evaluation list and labeled detail responses', () => {
    expect(
      ModelEvaluationsResponseSchema.parse({
        request_id: 'req-models',
        items: [
          {
            version: 'model-v1',
            created_at: to,
            evaluation_period: '2026-07-01 to 2026-07-18',
            has_labeled_ground_truth: true,
            available_metrics: ['mae', 'roc'],
            summary: 'Stable held-out evaluation',
          },
        ],
        page: 1,
        page_size: 25,
        total: 1,
      }),
    ).toMatchObject({ total: 1 })
    expect(ModelEvaluationDetailSchema.parse(evaluationDetail)).toEqual(evaluationDetail)
  })

  it('parses system status, liveness, and readiness independently', () => {
    expect(
      SystemStatusResponseSchema.parse({
        request_id: 'req-system',
        checked_at: to,
        overall_observation: 'Database ready; worker artifact unavailable',
        services: [
          {
            name: 'api',
            liveness: 'alive',
            readiness: 'ready',
            checked_at: to,
            detail: 'Database and migrations are ready',
          },
          {
            name: 'inference-worker',
            liveness: 'alive',
            readiness: 'not_ready',
            checked_at: to,
            detail: 'Artifact unavailable',
          },
        ],
        telemetry: {
          latest_ts: from,
          age_seconds: 3_600,
          fresh_sensor_count: 4,
          stale_sensor_count: 1,
          offline_sensor_count: 1,
        },
        diagnostics: { late_reading_count: 2, artifact_valid: false },
      }),
    ).toMatchObject({ request_id: 'req-system' })

    expect(
      LivenessResponseSchema.parse({ status: 'alive', request_id: 'req-live', checked_at: to }),
    ).toMatchObject({ status: 'alive' })
    expect(
      ReadinessResponseSchema.parse({
        status: 'not_ready',
        request_id: 'req-ready',
        checked_at: to,
        dependencies: [
          { name: 'database', status: 'not_ready', detail: 'Connection refused' },
        ],
      }),
    ).toMatchObject({ status: 'not_ready' })
  })
})

describe('query bounds and cross-field rules', () => {
  it('rejects reversed ranges and raw or bucketed history limits', () => {
    expect(
      TelemetryHistoryQuerySchema.safeParse({ deviceId: 'n1', from: to, to: from }).success,
    ).toBe(false)
    expect(
      TelemetryHistoryQuerySchema.safeParse({
        deviceId: 'n1',
        from,
        to,
        bucket: 'raw',
        limit: 5_001,
      }).success,
    ).toBe(false)
    expect(
      InferenceQuerySchema.safeParse({
        deviceId: 'n1',
        from,
        to,
        bucket: '1m',
        limit: 2_001,
      }).success,
    ).toBe(false)
  })

  it('enforces alert and pagination bounds', () => {
    expect(AlertEventsQuerySchema.safeParse({ limit: 201 }).success).toBe(false)
    expect(CurrentAlertsQuerySchema.safeParse({ page: 1, pageSize: 101 }).success).toBe(false)
    expect(ModelEvaluationsQuerySchema.safeParse({ page: 1, pageSize: 51 }).success).toBe(false)
  })

  it('allows open-ended alert-event time filters', () => {
    expect(AlertEventsQuerySchema.safeParse({ from }).success).toBe(true)
    expect(AlertEventsQuerySchema.safeParse({ to }).success).toBe(true)
  })

  it('enforces EDA ranges, bins, sample bounds, and differing correlation fields', () => {
    expect(EdaSummaryQuerySchema.safeParse({ from: to, to: from }).success).toBe(false)
    expect(
      EdaDistributionQuerySchema.safeParse({
        from,
        to,
        field: 'temperature_c',
        bins: 4,
      }).success,
    ).toBe(false)
    expect(
      EdaCorrelationQuerySchema.safeParse({
        from,
        to,
        xField: 'temperature_c',
        yField: 'temperature_c',
        maxPoints: 5_001,
      }).success,
    ).toBe(false)
  })
})

describe('semantic response validation', () => {
  it.each([
    ['telemetry', (value: number) => TelemetryPointSchema.safeParse({
      ...telemetryPoint,
      temperature_c: value,
    }).success],
    ['inference', (value: number) => InferencePointSchema.safeParse({
      ...inferencePoint,
      score: value,
    }).success],
    ['ROC point', (value: number) => RocPointSchema.safeParse({
      ...evaluationDetail.roc.points[0],
      fpr: value,
    }).success],
    ['precision-recall point', (value: number) => PrecisionRecallPointSchema.safeParse({
      ...evaluationDetail.precision_recall.points[0],
      precision: value,
    }).success],
    ['AUC', (value: number) => RocCurveSchema.safeParse({
      ...evaluationDetail.roc,
      auc: value,
    }).success],
    ['average precision', (value: number) => PrecisionRecallCurveSchema.safeParse({
      ...evaluationDetail.precision_recall,
      average_precision: value,
    }).success],
    ['generic metric', (value: number) => ModelEvaluationDetailSchema.safeParse({
      ...evaluationDetail,
      metrics: { mae: value },
    }).success],
    ['distribution summary', (value: number) => DistributionSummarySchema.safeParse({
      min: 20,
      max: 30,
      mean: value,
      median: 25,
      p05: 21,
      p95: 29,
    }).success],
    ['histogram bin bound', (value: number) => HistogramBinSchema.safeParse({
      start: 20,
      end: value,
      count: 10,
    }).success],
    ['scatter coordinate', (value: number) => CorrelationPointSchema.safeParse({
      ts: from,
      device_id: 'n1',
      x: value,
      y: 70,
      is_candidate_outlier: false,
    }).success],
    ['response correlation', (value: number) => EdaCorrelationResponseSchema.safeParse({
      request_id: 'req-eda-correlation',
      x_field: 'temperature_c',
      y_field: 'relative_humidity_pct',
      sample_count: 1,
      correlation: value,
      points: [],
      next_cursor: null,
    }).success],
  ] as const)('rejects non-finite %s numbers', (_name, parse) => {
    for (const value of [Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY]) {
      expect(parse(value)).toBe(false)
    }
  })

  it('rejects invalid alert action flags', () => {
    const invalid = {
      request_id: 'req-current',
      generated_at: to,
      items: [
        {
          alert_id: 'alert-1',
          device_id: 'n4',
          status: 'detected',
          detected_at: from,
          latest_event_ts: to,
          latest_event_id: 'event-1',
          score: 0.9,
          threshold: 0.8,
          model_version: 'model-v1',
          can_acknowledge: false,
          can_resolve: true,
        },
      ],
      page: 1,
      page_size: 25,
      total: 1,
    }
    expect(CurrentAlertsResponseSchema.safeParse(invalid).success).toBe(false)
  })

  it('rejects current-alert and model-evaluation rows beyond response page_size', () => {
    const currentItem = {
      alert_id: 'alert-1',
      device_id: 'n4',
      status: 'detected',
      detected_at: from,
      latest_event_ts: to,
      latest_event_id: 'event-1',
      score: 0.9,
      threshold: 0.8,
      model_version: 'model-v1',
      can_acknowledge: true,
      can_resolve: false,
    } as const
    expect(
      CurrentAlertsResponseSchema.safeParse({
        request_id: 'req-current',
        generated_at: to,
        items: [currentItem, { ...currentItem, alert_id: 'alert-2' }],
        page: 1,
        page_size: 1,
        total: 2,
      }).success,
    ).toBe(false)

    const modelItem = {
      version: 'model-v1',
      created_at: to,
      evaluation_period: '2026-07-01 to 2026-07-18',
      has_labeled_ground_truth: false,
      available_metrics: ['mae'],
      summary: 'Evaluation',
    }
    expect(
      ModelEvaluationsResponseSchema.safeParse({
        request_id: 'req-models',
        items: [modelItem, { ...modelItem, version: 'model-v2' }],
        page: 1,
        page_size: 1,
        total: 2,
      }).success,
    ).toBe(false)
  })

  it('accepts nested JSON system diagnostics', () => {
    expect(
      SystemStatusResponseSchema.safeParse({
        request_id: 'req-system',
        checked_at: to,
        overall_observation: 'MQTT lag observed',
        services: [],
        telemetry: {
          latest_ts: null,
          age_seconds: null,
          fresh_sensor_count: 0,
          stale_sensor_count: 0,
          offline_sensor_count: 0,
        },
        diagnostics: { mqtt: { lag_seconds: 3, topics: ['telemetry'] } },
      }).success,
    ).toBe(true)
  })

  it('bounds EDA summary collections without inventing pagination', () => {
    const candidate = {
      device_id: 'n1',
      start_ts: from,
      end_ts: to,
      reason: 'candidate',
      score: 0.9,
    } as const
    expect(
      EdaSummaryResponseSchema.safeParse({
        request_id: 'req-eda',
        scope: { device_ids: ['n1'], from, to, bucket: 'raw' },
        coverage: {
          expected_count: 1,
          observed_count: 1,
          coverage_pct: 100,
          gap_count: 0,
        },
        missingness: [],
        sensor_comparison: [],
        candidate_outliers: Array.from({ length: 501 }, () => candidate),
      }).success,
    ).toBe(false)
  })

  it('rejects undeclared metric keys', () => {
    expect(
      ModelEvaluationDetailSchema.safeParse({
        ...evaluationDetail,
        available_metrics: ['roc'],
        metrics: { mae: 0.12 },
      }).success,
    ).toBe(false)
  })

  it('rejects labeled-only structures on an unlabeled artifact', () => {
    expect(
      ModelEvaluationDetailSchema.safeParse({
        ...evaluationDetail,
        has_labeled_ground_truth: false,
      }).success,
    ).toBe(false)
  })
})

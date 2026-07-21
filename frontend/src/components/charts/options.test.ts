import { describe, expect, it } from 'vitest'
import type { CorrelationResponse, HistogramResponse } from '../../contracts/eda'
import type { ConfusionMatrix, PrecisionRecallCurve, RocCurve } from '../../contracts/modelEvaluation'
import { theme } from '../../theme/theme'
import {
  buildHistogramChartData,
  buildScatterChartData,
} from './edaOptions'
import {
  buildConfusionMatrixChartData,
  buildPrecisionRecallChartData,
  buildRocChartData,
} from './evaluationOptions'
import {
  buildOverviewSparklineData,
  buildTemporalChartData,
  buildTemporalSummary,
  type OverviewSparklineInput,
  type TemporalChartInput,
} from './temporalOptions'

const temporalInput: TemporalChartInput = {
  theme,
  sensorId: 'n2',
  from: '2026-07-19T09:00:00Z',
  to: '2026-07-19T10:00:00Z',
  telemetry: [
    {
      ts: '2026-07-19T09:00:00Z',
      temperature_c: 21,
      relative_humidity_pct: 50,
      sample_count: 1,
      gap_before: false,
    },
    {
      ts: '2026-07-19T09:15:00Z',
      temperature_c: 22,
      relative_humidity_pct: null,
      sample_count: 1,
      gap_before: true,
    },
    {
      ts: '2026-07-19T09:30:00Z',
      temperature_c: null,
      relative_humidity_pct: 54,
      sample_count: 1,
      gap_before: false,
    },
  ],
  inference: [
    {
      window_start_ts: '2026-07-19T09:00:00Z',
      window_end_ts: '2026-07-19T09:05:00Z',
      score: 0.2,
      threshold: 0.75,
      is_anomaly: false,
      model_version: 'model-v1',
      model_hash: 'model-hash',
      preprocessing_hash: 'preprocessing-hash',
      threshold_hash: 'threshold-hash',
    },
    {
      window_start_ts: '2026-07-19T09:10:00Z',
      window_end_ts: '2026-07-19T09:15:00Z',
      score: 0.91,
      threshold: 0.75,
      is_anomaly: true,
      model_version: 'model-v1',
      model_hash: 'model-hash',
      preprocessing_hash: 'preprocessing-hash',
      threshold_hash: 'threshold-hash',
    },
    {
      window_start_ts: '2026-07-19T09:25:00Z',
      window_end_ts: '2026-07-19T09:30:00Z',
      score: 0.82,
      threshold: 0.75,
      is_anomaly: true,
      model_version: 'model-v1',
      model_hash: 'model-hash',
      preprocessing_hash: 'preprocessing-hash',
      threshold_hash: 'threshold-hash',
    },
  ],
  alerts: [
    {
      event_id: 'event-1',
      alert_id: 'alert-1',
      event_ts: '2026-07-19T09:16:00Z',
      event_type: 'detected',
      device_id: 'n2',
      actor: 'detector',
      note: null,
      inference_result_window_start_ts: '2026-07-19T09:10:00Z',
      inference_result_window_end_ts: '2026-07-19T09:15:00Z',
      inference_model_version: 'model-v1',
    },
    {
      event_id: 'event-2',
      alert_id: 'alert-1',
      event_ts: '2026-07-19T09:20:00Z',
      event_type: 'acknowledged',
      device_id: 'n2',
      actor: 'operator',
      note: 'reviewing',
      inference_result_window_start_ts: '2026-07-19T09:10:00Z',
      inference_result_window_end_ts: '2026-07-19T09:15:00Z',
      inference_model_version: 'model-v1',
    },
  ],
}

const overviewSparklineInput: OverviewSparklineInput = {
  theme,
  sensorId: temporalInput.sensorId,
  from: temporalInput.from,
  to: temporalInput.to,
  telemetry: temporalInput.telemetry,
}

describe('temporal chart data', () => {
  it('maps ordered Date points, nullable readings, gap separators, scores, threshold, and anomaly intervals', () => {
    const before = structuredClone({
      telemetry: temporalInput.telemetry,
      inference: temporalInput.inference,
      alerts: temporalInput.alerts,
    })

    expect(buildTemporalChartData(temporalInput)).toEqual({
      temperature: [
        { x: new Date('2026-07-19T09:00:00Z'), y: 21 },
        { x: new Date('2026-07-19T09:15:00Z'), y: null },
        { x: new Date('2026-07-19T09:15:00Z'), y: 22 },
        { x: new Date('2026-07-19T09:30:00Z'), y: null },
      ],
      humidity: [
        { x: new Date('2026-07-19T09:00:00Z'), y: 50 },
        { x: new Date('2026-07-19T09:15:00Z'), y: null },
        { x: new Date('2026-07-19T09:15:00Z'), y: null },
        { x: new Date('2026-07-19T09:30:00Z'), y: 54 },
      ],
      scores: [
        { x: new Date('2026-07-19T09:05:00Z'), y: 0.2 },
        { x: new Date('2026-07-19T09:15:00Z'), y: 0.91 },
        { x: new Date('2026-07-19T09:30:00Z'), y: 0.82 },
      ],
      threshold: 0.75,
      anomalyIntervals: [
        {
          start: new Date('2026-07-19T09:10:00Z'),
          end: new Date('2026-07-19T09:15:00Z'),
        },
        {
          start: new Date('2026-07-19T09:25:00Z'),
          end: new Date('2026-07-19T09:30:00Z'),
        },
      ],
    })
    expect({
      telemetry: temporalInput.telemetry,
      inference: temporalInput.inference,
      alerts: temporalInput.alerts,
    }).toEqual(before)
  })

  it('uses is_anomaly alone for intervals and returns predictable empty data', () => {
    const inference = temporalInput.inference.map((point, index) => ({
      ...point,
      score: index === 0 ? 1 : 0,
      is_anomaly: index === 1,
    }))

    expect(buildTemporalChartData({ ...temporalInput, inference }).anomalyIntervals).toEqual([
      {
        start: new Date('2026-07-19T09:10:00Z'),
        end: new Date('2026-07-19T09:15:00Z'),
      },
    ])
    expect(buildTemporalChartData({ ...temporalInput, telemetry: [], inference: [] })).toEqual({
      temperature: [],
      humidity: [],
      scores: [],
      threshold: undefined,
      anomalyIntervals: [],
    })
  })

  it('builds a deterministic complete summary', () => {
    expect(buildTemporalSummary(temporalInput)).toBe(
      'Sensor n2 from 2026-07-19T09:00:00Z to 2026-07-19T10:00:00Z. 1 documented gap. Score threshold 0.75. 2 anomaly intervals. 1 detected alert.',
    )

    expect(buildTemporalSummary({ ...temporalInput, inference: [] }))
      .toContain('Score threshold unavailable.')
  })
})

describe('overview sparkline data', () => {
  it('maps both ordered nullable telemetry series to Date points without mutating input', () => {
    const before = structuredClone(overviewSparklineInput.telemetry)

    expect(buildOverviewSparklineData(overviewSparklineInput)).toEqual({
      temperature: [
        { x: new Date('2026-07-19T09:00:00Z'), y: 21 },
        { x: new Date('2026-07-19T09:15:00Z'), y: null },
        { x: new Date('2026-07-19T09:15:00Z'), y: 22 },
        { x: new Date('2026-07-19T09:30:00Z'), y: null },
      ],
      humidity: [
        { x: new Date('2026-07-19T09:00:00Z'), y: 50 },
        { x: new Date('2026-07-19T09:15:00Z'), y: null },
        { x: new Date('2026-07-19T09:15:00Z'), y: null },
        { x: new Date('2026-07-19T09:30:00Z'), y: 54 },
      ],
    })
    expect(buildOverviewSparklineData({ ...overviewSparklineInput, telemetry: [] })).toEqual({
      temperature: [],
      humidity: [],
    })
    expect(overviewSparklineInput.telemetry).toEqual(before)
  })
})

const histogram: HistogramResponse = {
  request_id: 'req-histogram',
  field: 'temperature_c',
  sample_count: 5,
  summary: { min: 0, max: 20, mean: 8, median: 7, p05: 1, p95: 18 },
  bins: [
    { start: 10, end: 20, count: 2 },
    { start: 0, end: 10, count: 3 },
  ],
}

const correlation: CorrelationResponse = {
  request_id: 'req-correlation',
  x_field: 'temperature_c',
  y_field: 'relative_humidity_pct',
  sample_count: 8,
  correlation: -0.42,
  points: [
    { ts: '2026-07-19T09:00:00Z', device_id: 'n1', x: 20, y: 60, is_candidate_outlier: false },
    { ts: '2026-07-19T09:05:00Z', device_id: 'n2', x: 30, y: 35, score: 0.9, is_candidate_outlier: true },
    { ts: '2026-07-19T09:10:00Z', device_id: 'n3', x: 22, y: 55, is_candidate_outlier: false },
  ],
  next_cursor: null,
}

describe('EDA chart data', () => {
  it('preserves histogram backend order and half-open labels without mutating bins', () => {
    const before = structuredClone(histogram)

    expect(buildHistogramChartData(histogram)).toEqual({
      labels: ['[10, 20)', '[0, 10)'],
      counts: [2, 3],
    })
    expect(buildHistogramChartData({ ...histogram, bins: [] })).toEqual({
      labels: [],
      counts: [],
    })
    expect(histogram).toEqual(before)
  })

  it('preserves scatter source order, identity, and candidate classification without mutation', () => {
    const before = structuredClone(correlation)

    expect(buildScatterChartData(correlation)).toEqual([
      {
        id: 'n1-2026-07-19T09:00:00Z-0',
        x: 20,
        y: 60,
        anomalous: false,
      },
      {
        id: 'n2-2026-07-19T09:05:00Z-1',
        x: 30,
        y: 35,
        anomalous: true,
      },
      {
        id: 'n3-2026-07-19T09:10:00Z-2',
        x: 22,
        y: 55,
        anomalous: false,
      },
    ])
    expect(buildScatterChartData({ ...correlation, points: [] })).toEqual([])
    expect(correlation).toEqual(before)
  })
})

describe('evaluation chart data', () => {
  const confusionMatrix: ConfusionMatrix = {
    labels: ['normal', 'anomaly'],
    matrix: [[8, 2], [3, 7]],
  }
  const roc: RocCurve = {
    auc: 0.91,
    points: [{ fpr: 0, tpr: 0 }, { fpr: 0.2, tpr: 0.8 }, { fpr: 1, tpr: 1 }],
  }
  const precisionRecall: PrecisionRecallCurve = {
    average_precision: 0.87,
    points: [{ recall: 0, precision: 1 }, { recall: 0.6, precision: 0.9 }, { recall: 1, precision: 0.5 }],
  }

  it('maps predicted columns, actual rows, every count, and a positive maximum without mutation', () => {
    const before = structuredClone(confusionMatrix)

    expect(buildConfusionMatrixChartData(confusionMatrix)).toEqual({
      xLabels: ['normal', 'anomaly'],
      yLabels: ['normal', 'anomaly'],
      rows: [
        { actual: 'normal', counts: [8, 2] },
        { actual: 'anomaly', counts: [3, 7] },
      ],
      maxCount: 8,
    })
    expect(buildConfusionMatrixChartData({
      labels: ['normal', 'anomaly'],
      matrix: [[0, 0], [0, 0]],
    }).maxCount).toBe(1)
    expect(confusionMatrix).toEqual(before)
  })

  it('preserves ROC and precision-recall point order without adding reference data', () => {
    const rocBefore = structuredClone(roc)
    const precisionRecallBefore = structuredClone(precisionRecall)

    expect(buildRocChartData(roc)).toEqual([
      { x: 0, y: 0 },
      { x: 0.2, y: 0.8 },
      { x: 1, y: 1 },
    ])
    expect(buildPrecisionRecallChartData(precisionRecall)).toEqual([
      { x: 0, y: 1 },
      { x: 0.6, y: 0.9 },
      { x: 1, y: 0.5 },
    ])
    expect(buildRocChartData({ ...roc, points: [] })).toEqual([])
    expect(buildPrecisionRecallChartData({ ...precisionRecall, points: [] })).toEqual([])
    expect(roc).toEqual(rocBefore)
    expect(precisionRecall).toEqual(precisionRecallBefore)
  })
})

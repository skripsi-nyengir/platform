import type {
  EdaCompleteSection,
  EdaComputeResponse,
  EdaJobSummary,
  EdaPeriodListResponse,
  EdaRunSummary,
  EdaSectionMetadata,
  EdaSectionName,
  EdaSectionResponse,
  RelationshipsPayload,
  StationarityPayload,
  UncertaintyPayload,
} from '../../contracts/eda'

const runId = 'run-b02-monthly-2026-02'
const weeklyRunId = 'run-b02-weekly-latest'
const canonicalRunId = 'run-b02-canonical-v3'
const cachedRunId = 'run-b02-custom-cache'
const publishedRunId = 'run-b02-custom-published'
const sourceHash = 'a'.repeat(64)
const configHash = 'b'.repeat(64)
const logicalKey = 'c'.repeat(64)
const payloadHash = 'd'.repeat(64)
const createdAt = '2026-07-26T08:00:00Z'

const monthlyScope = {
  device_id: 'b02f3872-39a2-4b6f-a4ec-045a287fde4b',
  time_zone: 'Asia/Jakarta',
  period_kind: 'monthly',
  from: '2026-02-01T00:00:00',
  to: '2026-03-01T00:00:00',
} as const

const runningScope = {
  ...monthlyScope,
  period_kind: 'custom',
  from: '2026-02-10T00:00:00',
  to: '2026-02-11T00:00:00',
} as const

const cachedScope = {
  ...monthlyScope,
  period_kind: 'custom',
  from: '2026-02-01T00:00:00',
  to: '2026-02-02T00:00:00',
} as const

const sectionNames = [
  'quality_overview',
  'joint_density',
  'univariate',
  'quality_excerpt',
  'temporal_coverage',
  'temporal_distribution',
  'relationships',
  'stationarity',
  'change_points',
  'uncertainty',
  'audit_metadata',
] as const satisfies readonly EdaSectionName[]

function completeMetadata(
  section: EdaSectionName,
  targetRunId = runId,
): Extract<EdaSectionMetadata, { status: 'complete' }> {
  return {
    run_id: targetRunId,
    section,
    status: 'complete',
    reason_code: null,
    detail: 'Bagian EDA tervalidasi untuk rentang aktif.',
    active_view: 'rule_screened_pairs',
    units: { temperature: '°C', relative_humidity: '%', time: 'second' },
    sample_counts: { raw_rows: 120, exact_pairs: 60, screened_pairs: 58, active_pairs: 58 },
    algorithm_version: 'b02-v3-live-1',
    config_hash: configHash,
    source_sha256: sourceHash,
    range_boundary: {
      from_censored: false,
      to_censored: false,
      from_open_ended: false,
      to_open_ended: false,
    },
    payload_sha256: payloadHash,
    created_at: createdAt,
  }
}

export const edaReadyMonthlyRun = {
  run_id: runId,
  logical_key: logicalKey,
  scope: monthlyScope,
  source_sha256: sourceHash,
  algorithm_version: 'b02-v3-live-1',
  config_hash: configHash,
  provenance_label: 'algorithm-equivalent range computation',
  canonical_release: false,
  completed_at: '2026-03-01T00:15:00Z',
  sections: sectionNames.map((section) => completeMetadata(section)),
} satisfies EdaRunSummary

export const edaReadyWeeklyRun = {
  ...edaReadyMonthlyRun,
  run_id: weeklyRunId,
  scope: {
    ...monthlyScope,
    period_kind: 'weekly',
    from: '2026-02-16T00:00:00',
    to: '2026-02-23T00:00:00',
  },
  sections: sectionNames.map((section) => completeMetadata(section, weeklyRunId)),
} satisfies EdaRunSummary

export const edaCanonicalRun = {
  ...edaReadyMonthlyRun,
  run_id: canonicalRunId,
  scope: {
    ...monthlyScope,
    period_kind: 'full_range',
    from: '2025-06-23T00:00:00',
    to: '2026-07-24T09:02:05',
  },
  provenance_label: 'published v3 release',
  canonical_release: true,
  sections: sectionNames.map((section) => completeMetadata(section, canonicalRunId)),
} satisfies EdaRunSummary

export const edaRunningCustomJob = {
  job_id: 'job-b02-custom-running',
  logical_key: 'e'.repeat(64),
  scope: runningScope,
  source_sha256: sourceHash,
  algorithm_version: 'b02-v3-live-1',
  config_hash: configHash,
  status: 'running',
  trigger_kind: 'api',
  attempt_count: 1,
  max_attempts: 3,
  terminal: false,
  created_at: '2026-07-26T07:00:00Z',
  started_at: '2026-07-26T07:00:02Z',
  completed_at: null,
  run_id: null,
  error_code: null,
  error_detail: null,
} satisfies EdaJobSummary

export const edaQueuedCustomJob = {
  ...edaRunningCustomJob,
  job_id: 'job-b02-custom-queued',
  status: 'queued',
  attempt_count: 0,
  started_at: null,
} satisfies EdaJobSummary

export const edaFailedJob = {
  ...edaRunningCustomJob,
  job_id: 'job-b02-custom-failed',
  logical_key: 'f'.repeat(64),
  status: 'failed',
  terminal: true,
  completed_at: '2026-07-26T07:05:00Z',
  error_code: 'eda_compute_failed',
  error_detail: 'Perhitungan EDA gagal setelah tiga percobaan.',
} satisfies EdaJobSummary

export const edaPublishedCustomRun = {
  ...edaReadyMonthlyRun,
  run_id: publishedRunId,
  logical_key: edaRunningCustomJob.logical_key,
  scope: runningScope,
  completed_at: '2026-07-26T07:04:00Z',
  sections: sectionNames.map((section) => completeMetadata(section, publishedRunId)),
} satisfies EdaRunSummary

export const edaSucceededJob = {
  ...edaRunningCustomJob,
  job_id: 'job-b02-custom-succeeded',
  status: 'succeeded',
  terminal: true,
  completed_at: '2026-07-26T07:04:00Z',
  run_id: publishedRunId,
} satisfies EdaJobSummary

const cachedCustomRun = {
  ...edaReadyMonthlyRun,
  run_id: cachedRunId,
  logical_key: '1'.repeat(64),
  scope: cachedScope,
  sections: sectionNames.map((section) => completeMetadata(section, cachedRunId)),
} satisfies EdaRunSummary

export const edaPeriodListResponse = {
  request_id: 'req-eda-periods',
  period_kind: 'monthly',
  items: [edaReadyMonthlyRun],
  next_cursor: null,
  returned_count: 1,
} satisfies EdaPeriodListResponse

export const edaCacheHitResponse = {
  request_id: 'req-eda-compute-cache',
  cache_hit: true,
  run: cachedCustomRun,
} satisfies EdaComputeResponse

export const edaRunningComputeResponse = {
  request_id: 'req-eda-compute-running',
  cache_hit: false,
  job: edaRunningCustomJob,
} satisfies EdaComputeResponse

export const edaQueuedComputeResponse = {
  request_id: 'req-eda-compute-queued',
  cache_hit: false,
  job: edaQueuedCustomJob,
} satisfies EdaComputeResponse

const completeBase = {
  ...completeMetadata('quality_overview'),
}

const univariateView = { histogram: [1], ecdf_count: [1], ecdf_fraction: [1] }

type RollingResult = RelationshipsPayload['rolling_pearson']['resolved_raw_pairs']['window_30m_gap_30s']

function rollingResult(
  windowSeconds: 900 | 1800 | 3600 | 10800,
  gapSeconds: 15 | 30 | 60,
): RollingResult {
  return {
    status: 'complete',
    reason_code: null,
    window_seconds: windowSeconds,
    gap_boundary_seconds: gapSeconds,
    eligible_window_count: 1,
    total_endpoint_count: 300,
    minimum: 0.2,
    q05: 0.2,
    q25: 0.2,
    median: 0.2,
    q75: 0.2,
    q95: 0.2,
    maximum: 0.2,
    plotted_end_timestamps: [1],
    plotted_correlations: [0.2],
  }
}

const rollingVariants: RelationshipsPayload['rolling_pearson']['resolved_raw_pairs'] = {
  window_15m_gap_30s: rollingResult(900, 30),
  window_30m_gap_15s: rollingResult(1800, 15),
  window_30m_gap_30s: rollingResult(1800, 30),
  window_30m_gap_60s: rollingResult(1800, 60),
  window_60m_gap_30s: rollingResult(3600, 30),
  window_180m_gap_30s: rollingResult(10800, 30),
}

const constantSequence: StationarityPayload['sensitivity'][number]['channels']['suhu']['autocorrelation'] = {
  status: 'constant',
  method: 'acf_fft',
  values: [],
  maximum_lag: 72,
  error: null,
}

const stationarityChannel: StationarityPayload['sensitivity'][number]['channels']['suhu'] = {
  autocorrelation: constantSequence,
  partial_autocorrelation: { ...constantSequence, method: 'pacf_ywm' },
  spectrum: { status: 'constant', frequencies: [], power: [], error: null },
  stl: { status: 'constant', seasonal: [], trend: [], residual: [], error: null },
}

function bootstrapBlock(blockDays: 7 | 14 | 28): UncertaintyPayload['blocks']['7'] {
  return {
    status: 'complete',
    reason_code: null,
    intervals: [
      {
        statistic: 'pearson', block_days: blockDays, status: 'ok', pair_count: 90,
        run_count: 1, replicate_count: 2000, estimate: 0.2, lower: 0.1, upper: 0.3,
      },
      {
        statistic: 'spearman', block_days: blockDays, status: 'ok', pair_count: 90,
        run_count: 1, replicate_count: 2000, estimate: 0.2, lower: 0.1, upper: 0.3,
      },
    ],
  }
}

export const edaCompleteSections: EdaCompleteSection[] = [
  {
    ...completeBase,
    section: 'quality_overview',
    payload: {
      source_audit: { row_count: 120 },
      count_conservation: { status: 'pass' },
      quality_metrics: { excluded_pairs: 2 },
    },
  },
  {
    ...completeBase,
    section: 'joint_density',
    payload: {
      edges: { temperature_c: [0, 60], relative_humidity_pct: [0, 100] },
      views: {
        resolved_raw_pairs: { histogram: [[60]] },
        rule_screened_pairs: { histogram: [[58]] },
      },
    },
  },
  {
    ...completeBase,
    section: 'univariate',
    payload: {
      channels: {
        Suhu: {
          unit: '°C', edges: [0, 60],
          views: { resolved_raw_pairs: univariateView, rule_screened_pairs: univariateView },
        },
        RH: {
          unit: '%', edges: [0, 100],
          views: { resolved_raw_pairs: univariateView, rule_screened_pairs: univariateView },
        },
      },
    },
  },
  {
    ...completeBase,
    section: 'quality_excerpt',
    payload: {
      selection_kind: 'dense_fallback',
      from: '2026-02-01T00:00:00',
      to: '2026-02-01T00:00:06',
      records: [{ timestamp: '2026-02-01T00:00:00', temperature_c: 25 }],
    },
  },
  {
    ...completeBase,
    section: 'temporal_coverage',
    payload: {
      calendar_semantics: { time_zone: 'Asia/Jakarta' },
      views: { resolved_raw_pairs: { bins: [] } },
    },
  },
  {
    ...completeBase,
    section: 'temporal_distribution',
    payload: {
      cadence: { expected_seconds: 6 },
      views: { rule_screened_pairs: { hourly: [] } },
    },
  },
  {
    ...completeBase,
    section: 'relationships',
    payload: {
      static: {
        resolved_raw_pairs: { status: 'ok', pair_count: 30, pearson: 0.2, spearman: 0.3 },
        rule_screened_pairs: { status: 'ok', pair_count: 30, pearson: 0.2, spearman: 0.3 },
      },
      rolling_pearson: {
        resolved_raw_pairs: rollingVariants,
        rule_screened_pairs: rollingVariants,
      },
    },
  },
  {
    ...completeBase,
    section: 'stationarity',
    payload: {
      eligibility_tier: 'sensitivity',
      primary: null,
      sensitivity: [{
        status: 'ok',
        start: '2025-07-01T00:00:00+07:00',
        end: '2025-07-15T00:00:00+07:00',
        hours: 336,
        channels: { suhu: stationarityChannel, rh: stationarityChannel },
      }],
    },
  },
  {
    ...completeBase,
    section: 'change_points',
    payload: {
      blocks: [{
        status: 'constant',
        pair_count: 90,
        start_day: 1,
        end_day: 90,
        scale_median: [25, 60],
        scale_mad: [0, 0],
        constant_channels: [0, 1],
        stable_changes: [],
        confirmations: [],
      }],
    },
  },
  {
    ...completeBase,
    section: 'uncertainty',
    payload: {
      method: 'paired_moving_block_bootstrap',
      confidence_level: 0.95,
      seed: 20260724,
      replicates: 2000,
      blocks: { '7': bootstrapBlock(7), '14': bootstrapBlock(14), '28': bootstrapBlock(28) },
      sensitivity_status: 'robust',
    },
  },
  {
    ...completeBase,
    section: 'audit_metadata',
    payload: {
      dataset_id: 'bivariate_b02f3872_v1',
      source_manifest_sha256: sourceHash,
      release_id: 'bivariate_b02f3872_eda_v3',
      seed: 20260724,
      dependencies: { numpy: '2.4.6' },
    },
  },
]

export const edaNotEligibleSection = {
  ...completeMetadata('stationarity'),
  status: 'not_eligible',
  reason_code: 'insufficient_stationarity_primary_tier',
  detail: 'Median per jam belum cukup untuk analisis stasioneritas utama.',
  payload_sha256: null,
  payload: null,
} satisfies EdaSectionResponse

export const edaFailedSection = {
  ...completeMetadata('relationships'),
  status: 'failed',
  reason_code: 'section_compute_failed',
  detail: 'Perhitungan hubungan gagal dan dapat dicoba kembali.',
  payload_sha256: null,
  payload: null,
} satisfies EdaSectionResponse

export const edaChangePointsNotEligibleSection = {
  ...completeMetadata('change_points'),
  status: 'not_eligible',
  reason_code: 'insufficient_daily_medians',
  detail: 'Median harian belum cukup untuk kandidat perubahan rezim.',
  payload_sha256: null,
  payload: null,
} satisfies EdaSectionResponse

export const edaUncertaintyNotEligibleSection = {
  ...completeMetadata('uncertainty'),
  status: 'not_eligible',
  reason_code: 'block_longer_than_run',
  detail: 'Panjang blok bootstrap melampaui rentang run.',
  payload_sha256: null,
  payload: null,
} satisfies EdaSectionResponse

export const edaSectionsByName = new Map<EdaSectionName, EdaCompleteSection>(
  edaCompleteSections.map((section) => [section.section, section]),
)

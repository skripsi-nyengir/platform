import type {
  ModelEvaluationDetail,
  ModelEvaluationSummary,
} from '../../contracts/modelEvaluation'

interface PilotModel {
  modelKey: string
  displayName: string
  scoreKey: string
  threshold: number
  predictedWindows: number
  metrics: Readonly<Record<string, unknown>>
}

const sourceCommit = '6d265f0b3d3c91097e2295a43c6a6dee034374d8'
const sourcePath = 'notebooks/step10/summaries/step10_comparison_summary.json'
const sourceSha256 = 'ed03bf3d823d7a47c3f18f946d6222844476cc83ee28bdd64a436df356caa18d'
const pilotDisclaimer =
  'Snapshot pilot Dandy berasal dari satu seed/run; test sudah diamati, belum merupakan evaluasi independen/final, dan seluruh model gagal skenario stuck.'

const pilotModels = Object.freeze([
  {
    modelKey: 'lstm-ae',
    displayName: 'LSTM-AE',
    scoreKey: 'global_mae',
    threshold: 0.009740831330418587,
    predictedWindows: 2_358,
    metrics: { window_f1: 0.617941823515033, stuck_event_hit_rate: 0 },
  },
  {
    modelKey: 'usad',
    displayName: 'USAD',
    scoreKey: 'averaged_global_l2',
    threshold: 0.30791249647736557,
    predictedWindows: 3_378,
    metrics: { window_f1: 0.43122676579925645, stuck_event_hit_rate: 0 },
  },
  {
    modelKey: 'cfc-autoencoder',
    displayName: 'CfC Autoencoder',
    scoreKey: 'global_mse',
    threshold: 0.000003889578908911372,
    predictedWindows: 2_433,
    metrics: { window_f1: 0.3917426788286126, stuck_event_hit_rate: 0 },
  },
  {
    modelKey: 'ewma',
    displayName: 'EWMA',
    scoreKey: 'global_mae',
    threshold: 0.025326583255082382,
    predictedWindows: 3_382,
    metrics: { window_f1: 0.33313782991202345, stuck_event_hit_rate: 0 },
  },
  {
    modelKey: 'pca',
    displayName: 'PCA',
    scoreKey: 'global_mae',
    threshold: 0.022622425761073855,
    predictedWindows: 3_448,
    metrics: { window_f1: 0.344721096313453, stuck_event_hit_rate: 0 },
  },
  {
    modelKey: 'mtad-gat',
    displayName: 'MTAD-GAT',
    scoreKey: 'fused_score',
    threshold: 0.7346822699514213,
    predictedWindows: 647,
    metrics: { window_f1: 0.2736660929432014, stuck_event_hit_rate: 0 },
  },
  {
    modelKey: 'wsn-dense-ae',
    displayName: 'WSN Dense AE',
    scoreKey: 'global_mse',
    threshold: 0.001566833149991076,
    predictedWindows: 6_518,
    metrics: { window_f1: 0.2780269058295964, stuck_event_hit_rate: 0 },
  },
] satisfies readonly PilotModel[])

function evaluationSummary(model: PilotModel): Readonly<ModelEvaluationSummary> {
  return Object.freeze({
    version: `reported-dandy-pilot-${model.modelKey}`,
    model: model.displayName,
    track: 'reported_dandy_pilot',
    label: 'Pilot Dandy (satu run; bukan hasil platform)',
    score_key: model.scoreKey,
    score_semantics: 'reported Dandy pilot metric; separate from preview replay',
    evaluation_period: 'single observed synthetic test run',
    validation_only: false,
    test_evaluated: true,
    n_val_windows: model.predictedWindows,
    threshold: model.threshold,
    threshold_policy: {
      source: 'reported_dandy_pilot',
      comparator: '>',
    },
    has_labeled_ground_truth: true,
    available_metrics: [
      'composite_primary',
      'window_f1',
      'window_precision',
      'window_recall',
      'event_hit_rate',
      'clean_test_fpr',
      'alert_rate',
      'stuck_event_hit_rate',
    ],
    summary: pilotDisclaimer,
    model_key: model.modelKey,
    report_source: 'reported_dandy_pilot',
    label_source: 'synthetic_injection',
    evaluation_kind: 'comparison_snapshot',
    test_observed: true,
    independent_final: false,
    source_commit: sourceCommit,
    source_path: sourcePath,
    source_sha256: sourceSha256,
  })
}

export const modelEvaluationSummaries = Object.freeze(pilotModels.map(evaluationSummary))

function evaluationDetail(
  summary: ModelEvaluationSummary,
  model: PilotModel,
): Readonly<ModelEvaluationDetail> {
  return Object.freeze({
    ...summary,
    request_id: `req_model_${summary.version}`,
    model_hash: null,
    preprocessing_hash: null,
    threshold_hash: null,
    metrics: {
      reported_threshold: model.threshold,
      n_predicted_windows: model.predictedWindows,
      ...model.metrics,
    },
    notes: 'Seluruh model memiliki stuck_event_hit_rate=0.0.',
  })
}

export const modelEvaluationDetails = Object.freeze(
  Object.fromEntries(
    modelEvaluationSummaries.map((summary, index) => [
      summary.version,
      evaluationDetail(summary, pilotModels[index] as PilotModel),
    ]),
  ),
)

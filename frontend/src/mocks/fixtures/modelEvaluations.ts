import type {
  ModelEvaluationDetail,
  ModelEvaluationSummary,
} from '../../contracts/modelEvaluation'

export const modelEvaluationSummaries = Object.freeze([
  Object.freeze({
    version: 'model-v2',
    created_at: '2026-07-19T08:00:00Z',
    evaluation_period: '2026-07-12 to 2026-07-18',
    has_labeled_ground_truth: true,
    available_metrics: ['accuracy', 'f1', 'confusion_matrix', 'roc', 'precision_recall'],
    summary: 'Selected production candidate evaluation',
  } satisfies ModelEvaluationSummary),
  Object.freeze({
    version: 'model-v1',
    created_at: '2026-07-19T07:00:00Z',
    evaluation_period: '2026-07-05 to 2026-07-11',
    has_labeled_ground_truth: true,
    available_metrics: ['accuracy', 'f1', 'confusion_matrix', 'roc', 'precision_recall'],
    summary: 'Current deterministic baseline evaluation',
  } satisfies ModelEvaluationSummary),
])

function evaluationDetail(version: 'model-v1' | 'model-v2'): Readonly<ModelEvaluationDetail> {
  const summary = modelEvaluationSummaries.find((item) => item.version === version)
  if (summary === undefined) throw new Error(`Missing model summary for ${version}`)
  return Object.freeze({
    request_id: `req_model_${version}`,
    version,
    created_at: summary.created_at,
    evaluation_period: summary.evaluation_period,
    model_hash: `sha256:${version}`,
    preprocessing_hash: 'sha256:preprocessing-v1',
    threshold_hash: 'sha256:threshold-v1',
    has_labeled_ground_truth: true,
    available_metrics: summary.available_metrics,
    metrics: { accuracy: version === 'model-v2' ? 0.96 : 0.94, f1: version === 'model-v2' ? 0.91 : 0.88 },
    confusion_matrix: {
      labels: ['normal', 'anomaly'],
      matrix: [
        [92, 3],
        [2, 13],
      ],
    },
    roc: {
      auc: version === 'model-v2' ? 0.97 : 0.95,
      points: [
        { fpr: 0, tpr: 0 },
        { fpr: 0.08, tpr: 0.9 },
        { fpr: 1, tpr: 1 },
      ],
    },
    precision_recall: {
      average_precision: version === 'model-v2' ? 0.93 : 0.9,
      points: [
        { recall: 0, precision: 1 },
        { recall: 0.9, precision: 0.88 },
        { recall: 1, precision: 0.5 },
      ],
    },
    notes: 'Deterministic held-out labeled evaluation',
  })
}

export const modelEvaluationDetails = Object.freeze({
  'model-v1': evaluationDetail('model-v1'),
  'model-v2': evaluationDetail('model-v2'),
})

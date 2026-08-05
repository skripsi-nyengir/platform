import { z } from 'zod'

const FractionSchema = z.number().min(0).max(1)
const Sha256Schema = z.string().regex(/^[0-9a-f]{64}$/)

export const OfflineEvaluationModelFamilySchema = z.enum([
  'conv1d',
  'gru',
  'lstm',
  'rnn',
  'transformer',
])
export type OfflineEvaluationModelFamily = z.infer<
  typeof OfflineEvaluationModelFamilySchema
>

export const OfflineEvaluationScopeMetricsSchema = z
  .strictObject({
    accuracy: FractionSchema,
    precision: FractionSchema,
    recall: FractionSchema,
    f1: FractionSchema,
    tn: z.number().int().nonnegative(),
    fp: z.number().int().nonnegative(),
    fn: z.number().int().nonnegative(),
    tp: z.number().int().nonnegative(),
    n_evaluated: z.number().int().positive(),
  })
  .superRefine((metrics, context) => {
    const total = metrics.tn + metrics.fp + metrics.fn + metrics.tp
    if (total !== metrics.n_evaluated) {
      context.addIssue({
        code: 'custom',
        message: 'scope confusion counts must sum to n_evaluated',
        path: ['n_evaluated'],
      })
      return
    }

    const derived = {
      accuracy: (metrics.tn + metrics.tp) / total,
      precision: metrics.tp + metrics.fp === 0 ? 0 : metrics.tp / (metrics.tp + metrics.fp),
      recall: metrics.tp + metrics.fn === 0 ? 0 : metrics.tp / (metrics.tp + metrics.fn),
      f1:
        2 * metrics.tp + metrics.fp + metrics.fn === 0
          ? 0
          : (2 * metrics.tp) / (2 * metrics.tp + metrics.fp + metrics.fn),
    }

    for (const name of ['accuracy', 'precision', 'recall', 'f1'] as const) {
      if (Math.abs(metrics[name] - derived[name]) > 1e-12) {
        context.addIssue({
          code: 'custom',
          message: `scope ${name} must match confusion counts`,
          path: [name],
        })
      }
    }
  })
export type OfflineEvaluationScopeMetrics = z.infer<
  typeof OfflineEvaluationScopeMetricsSchema
>

const OfflineEvaluationSourceFileSchema = z.strictObject({
  filename: z.string().min(1),
  sha256: Sha256Schema,
})

const OfflineEvaluationArtifactCheckSchema = OfflineEvaluationSourceFileSchema.extend({
  role: z.enum(['step5_model_identity', 'step7_metric_cross_check']),
  consistency: z.enum(['matched', 'conflict']),
  note: z.string().min(1),
})

export const OfflineEvaluationContextSchema = z
  .strictObject({
    dataset_reference: z.literal('b02f3872_ruang_produksi_v3_march07'),
    evaluation_split: z.literal('val_injected'),
    test_consumed: z.literal(false),
    primary_scope: z.literal('non_overlapping_evaluation_bins'),
    primary_metric: z.literal('f1'),
    n_points_total: z.number().int().positive(),
    n_points_evaluated: z.number().int().positive(),
    n_model_windows: z.number().int().positive(),
    n_positive_windows: z.number().int().positive(),
    n_events: z.number().int().positive(),
    evaluation_bin_size_points: z.number().int().positive(),
    n_evaluation_bins: z.number().int().positive(),
    n_skipped_bins: z.number().int().nonnegative(),
  })
  .superRefine((evaluation, context) => {
    if (evaluation.n_points_evaluated > evaluation.n_points_total) {
      context.addIssue({
        code: 'custom',
        message: 'evaluated points cannot exceed total points',
        path: ['n_points_evaluated'],
      })
    }
    if (evaluation.n_positive_windows > evaluation.n_model_windows) {
      context.addIssue({
        code: 'custom',
        message: 'positive windows cannot exceed model windows',
        path: ['n_positive_windows'],
      })
    }
  })
export type OfflineEvaluationContext = z.infer<typeof OfflineEvaluationContextSchema>

export const OfflineEvaluationItemSchema = z.strictObject({
  model_family: OfflineEvaluationModelFamilySchema,
  model_sha256: Sha256Schema,
  threshold: z.strictObject({
    value: z.number().nonnegative(),
    method: z.literal('clean_percentile_99_5'),
    percentile: z.literal(99.5),
    calibration_split: z.literal('clean_validation'),
    comparison: z.literal('strict_gt'),
    score_unit: z.literal('timestamp'),
    uses_anomaly_labels: z.literal(false),
    clean_alert_rate: FractionSchema,
  }),
  scopes: z.strictObject({
    timestamp: OfflineEvaluationScopeMetricsSchema,
    overlapping_model_windows: OfflineEvaluationScopeMetricsSchema,
    non_overlapping_evaluation_bins: OfflineEvaluationScopeMetricsSchema,
  }),
  point_auc: z.strictObject({
    roc: FractionSchema,
    pr_trapezoidal: FractionSchema,
    pr_definition: z.literal('trapezoidal_precision_recall_auc'),
    score_unit: z.literal('timestamp'),
  }),
  provenance: z.strictObject({
    metric_authority: z.literal('executed_step7_notebook_output'),
    step5_notebook: OfflineEvaluationSourceFileSchema,
    step7_notebook: OfflineEvaluationSourceFileSchema,
    artifact_checks: z.array(OfflineEvaluationArtifactCheckSchema).max(3),
  }),
})
export type OfflineEvaluationItem = z.infer<typeof OfflineEvaluationItemSchema>

const MODEL_ORDER: OfflineEvaluationModelFamily[] = [
  'conv1d',
  'gru',
  'lstm',
  'rnn',
  'transformer',
]

export const OfflineEvaluationsResponseSchema = z
  .strictObject({
    evaluation: OfflineEvaluationContextSchema,
    items: z.array(OfflineEvaluationItemSchema).length(5),
  })
  .refine(
    (value) =>
      value.items.every((item, index) => item.model_family === MODEL_ORDER[index]),
    {
      message: 'items must contain the five trained model families in canonical order',
      path: ['items'],
    },
  )
export type OfflineEvaluationsResponse = z.infer<typeof OfflineEvaluationsResponseSchema>

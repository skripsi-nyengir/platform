import { z } from 'zod'

const MetricIdentifierSchema = z.string().min(1)
const LabeledMetricIdentifierSchema = z.enum(['confusion_matrix', 'roc', 'precision_recall'])

export const ThresholdPolicySchema = z.strictObject({
  source: z.string().min(1).optional(),
  source_split: z.string().min(1).optional(),
  percentile: z.number().optional(),
  comparison: z.string().min(1).optional(),
  comparator: z.string().min(1).optional(),
}).catchall(z.unknown())

export const ValidationTrackFieldsSchema = z.strictObject({
  version: z.string().min(1),
  model: z.string().min(1),
  track: z.string().min(1),
  label: z.string().min(1),
  score_key: z.string().min(1),
  score_semantics: z.string().min(1),
  evaluation_period: z.string().min(1),
  validation_only: z.boolean(),
  test_evaluated: z.boolean(),
  n_val_windows: z.number().int().positive(),
  threshold: z.number(),
  threshold_policy: ThresholdPolicySchema,
  has_labeled_ground_truth: z.boolean(),
  available_metrics: z.array(MetricIdentifierSchema).max(500),
  summary: z.string().min(1),
  model_key: z.string().nullable(),
  report_source: z.enum([
    'legacy_m1_fixture',
    'platform_computed',
    'reported_dandy_pilot',
  ]),
  label_source: z.enum(['none', 'synthetic_injection', 'expert', 'natural']),
  evaluation_kind: z.enum([
    'validation_threshold',
    'synthetic_test',
    'clean_test',
    'comparison_snapshot',
  ]),
  test_observed: z.boolean(),
  independent_final: z.boolean(),
  source_commit: z.string().nullable(),
  source_path: z.string().nullable(),
  source_sha256: z.string().nullable(),
})

export const ModelEvaluationSummarySchema = ValidationTrackFieldsSchema
export type ModelEvaluationSummary = z.infer<typeof ModelEvaluationSummarySchema>

export const ModelEvaluationsQuerySchema = z.strictObject({
  page: z.number().int().min(1).default(1),
  pageSize: z.number().int().min(1).max(50).default(25),
})
export type ModelEvaluationsQuery = z.input<typeof ModelEvaluationsQuerySchema>

export const ModelEvaluationsResponseSchema = z
  .strictObject({
    request_id: z.string(),
    items: z.array(ModelEvaluationSummarySchema).max(50),
    page: z.number().int().min(1),
    page_size: z.number().int().min(1).max(50),
    total: z.number().int().nonnegative(),
  })
  .superRefine((value, context) => {
    if (value.total < value.items.length) {
      context.addIssue({
        code: 'custom',
        message: 'total must be at least the number of returned items',
        path: ['total'],
      })
    }
    if (value.items.length > value.page_size) {
      context.addIssue({
        code: 'custom',
        message: 'items length must not exceed page_size',
        path: ['items'],
      })
    }
  })
export type ModelEvaluationsResponse = z.infer<typeof ModelEvaluationsResponseSchema>

export const ConfusionMatrixSchema = z
  .strictObject({
    labels: z.array(z.string()).min(2).max(500),
    matrix: z.array(z.array(z.number().int().nonnegative()).max(500)).min(2).max(500),
  })
  .refine(
    (value) =>
      value.matrix.length === value.labels.length &&
      value.matrix.every((row) => row.length === value.labels.length),
    { message: 'matrix dimensions must match labels', path: ['matrix'] },
  )
export type ConfusionMatrix = z.infer<typeof ConfusionMatrixSchema>

export const RocPointSchema = z.strictObject({
  fpr: z.number().min(0).max(1),
  tpr: z.number().min(0).max(1),
})

export const RocCurveSchema = z.strictObject({
  auc: z.number().min(0).max(1),
  points: z.array(RocPointSchema).max(5_000),
})
export type RocCurve = z.infer<typeof RocCurveSchema>

export const PrecisionRecallPointSchema = z.strictObject({
  recall: z.number().min(0).max(1),
  precision: z.number().min(0).max(1),
})

export const PrecisionRecallCurveSchema = z.strictObject({
  average_precision: z.number().min(0).max(1),
  points: z.array(PrecisionRecallPointSchema).max(5_000),
})
export type PrecisionRecallCurve = z.infer<typeof PrecisionRecallCurveSchema>

export const ModelEvaluationDetailSchema = ValidationTrackFieldsSchema
  .extend({
    request_id: z.string(),
    model_hash: z.string().nullable(),
    preprocessing_hash: z.string().nullable(),
    threshold_hash: z.string().nullable(),
    metrics: z.record(z.string(), z.unknown()),
    confusion_matrix: ConfusionMatrixSchema.optional(),
    roc: RocCurveSchema.optional(),
    precision_recall: PrecisionRecallCurveSchema.optional(),
    notes: z.string().nullable(),
  })
  .superRefine((value, context) => {
    const declared = new Set(value.available_metrics)
    if (Object.keys(value.metrics).length > 500) {
      context.addIssue({
        code: 'custom',
        message: 'metrics must contain at most 500 entries',
        path: ['metrics'],
      })
    }

    const labeledStructures = [
      ['confusion_matrix', value.confusion_matrix],
      ['roc', value.roc],
      ['precision_recall', value.precision_recall],
    ] as const
    for (const [identifier, structure] of labeledStructures) {
      if (structure !== undefined && !value.has_labeled_ground_truth) {
        context.addIssue({
          code: 'custom',
          message: `${identifier} requires labeled ground truth`,
          path: [identifier],
        })
      }
      if (structure !== undefined && !declared.has(identifier)) {
        context.addIssue({
          code: 'custom',
          message: `${identifier} is not declared in available_metrics`,
          path: [identifier],
        })
      }
    }

    if (!value.has_labeled_ground_truth) {
      for (const identifier of LabeledMetricIdentifierSchema.options) {
        if (declared.has(identifier)) {
          context.addIssue({
            code: 'custom',
            message: `${identifier} cannot be available without labeled ground truth`,
            path: ['available_metrics'],
          })
        }
      }
    }
  })
export type ModelEvaluationDetail = z.infer<typeof ModelEvaluationDetailSchema>

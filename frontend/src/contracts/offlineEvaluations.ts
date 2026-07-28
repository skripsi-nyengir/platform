import { z } from 'zod'
import { Rfc3339Schema } from './common'

const FractionSchema = z.number().min(0).max(1)

export const OfflineEvaluationItemSchema = z.strictObject({
  model_family: z.string().min(1),
  model_sha256: z.string().regex(/^[0-9a-f]{64}$/),
  dataset_reference: z.string().min(1),
  forward_validation: z.strictObject({
    recon_max_abs_diff: z.number().nonnegative(),
    score_rel_error: z.number().nonnegative(),
    passed: z.boolean(),
  }),
  threshold: z.strictObject({
    value: z.number().nonnegative(),
    policy: z.string().min(1),
    alpha: FractionSchema,
    comparison: z.string().min(1),
  }),
  n_val_windows: z.number().int().nonnegative(),
  n_test_windows: z.number().int().nonnegative(),
  n_events: z.number().int().nonnegative(),
  n_positive_windows: z.number().int().nonnegative(),
  metrics: z.strictObject({
    window_precision: FractionSchema,
    window_recall: FractionSchema,
    window_f1: FractionSchema,
    event_hit_rate: FractionSchema,
    event_hit_by_family: z.record(z.string().min(1), FractionSchema),
    clean_test_fpr: FractionSchema,
    composite_fc1: FractionSchema,
    alert_rate: z.number().nonnegative(),
  }),
  provenance: z.strictObject({
    forward: z.string().min(1),
    torch_version: z.string().min(1),
    computed_at: Rfc3339Schema,
  }),
})
export type OfflineEvaluationItem = z.infer<typeof OfflineEvaluationItemSchema>

export const OfflineEvaluationsResponseSchema = z.strictObject({
  items: z.array(OfflineEvaluationItemSchema).min(1),
})
export type OfflineEvaluationsResponse = z.infer<typeof OfflineEvaluationsResponseSchema>

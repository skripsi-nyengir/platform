import { z } from 'zod'

const ReportedModelFieldsSchema = z.strictObject({
  display_name: z.string().min(1),
  architecture: z.record(z.string().min(1), z.unknown()),
  param_count: z.number().int(),
  best_val_mse: z.number(),
  best_epoch: z.number().int(),
  model_sha256: z.string().regex(/^[0-9a-f]{64}$/),
  dataset_reference: z.literal('b02f3872_ruang_produksi_v3_march07'),
  window_size: z.literal(30),
  features: z.tuple([z.literal('suhu'), z.literal('rh')]),
  score_semantics: z.literal('window_mean_squared_reconstruction_error'),
  report_source: z.literal('reported_model_registry'),
  summary: z.string().min(1),
})

export const ModelRegistryItemSchema = z.discriminatedUnion('id', [
  ReportedModelFieldsSchema.extend({
    id: z.literal('transformer_step5'),
    family: z.literal('transformer'),
  }),
  ReportedModelFieldsSchema.extend({
    id: z.literal('conv1d_step5'),
    family: z.literal('conv1d'),
  }),
  ReportedModelFieldsSchema.extend({
    id: z.literal('lstm_step5'),
    family: z.literal('lstm'),
  }),
])
export type ModelRegistryItem = z.infer<typeof ModelRegistryItemSchema>

export const ModelRegistryResponseSchema = z
  .strictObject({
    items: z.array(ModelRegistryItemSchema).length(3),
  })
  .refine((value) => new Set(value.items.map((item) => item.id)).size === 3, {
    message: 'items must contain each registered model exactly once',
    path: ['items'],
  })
export type ModelRegistryResponse = z.infer<typeof ModelRegistryResponseSchema>

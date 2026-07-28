import type {
  ModelRegistryItem,
  ModelRegistryResponse,
} from '../../contracts/modelRegistry'

const sharedFacts: Pick<
  ModelRegistryItem,
  'dataset_reference' | 'window_size' | 'features' | 'score_semantics' | 'report_source'
> = {
  dataset_reference: 'b02f3872_ruang_produksi_v3_march07',
  window_size: 30,
  features: ['suhu', 'rh'],
  score_semantics: 'window_mean_squared_reconstruction_error',
  report_source: 'reported_model_registry',
}

export const modelRegistryResponse = {
  items: [
    {
      ...sharedFacts,
      id: 'transformer_step5',
      family: 'transformer',
      display_name: 'Transformer Autoencoder',
      architecture: {
        d_model: 32,
        n_heads: 4,
        num_layers: 2,
        dim_feedforward: 64,
        dropout: 0.1,
      },
      param_count: 44_002,
      best_val_mse: 5.157235643571508e-05,
      best_epoch: 8,
      model_sha256: '1'.repeat(64),
      summary: 'Transformer reconstruction model dengan metrik validasi yang dilaporkan dari training.',
    },
    {
      ...sharedFacts,
      id: 'conv1d_step5',
      family: 'conv1d',
      display_name: 'Conv1D Autoencoder',
      architecture: {
        channels: [16, 32],
        kernel_size: 3,
        latent_dim: 16,
        dropout: 0.1,
      },
      param_count: 7_474,
      best_val_mse: 1.8269720032613215e-05,
      best_epoch: 5,
      model_sha256: '2'.repeat(64),
      summary: 'Conv1D reconstruction model dengan metrik validasi yang dilaporkan dari training.',
    },
    {
      ...sharedFacts,
      id: 'lstm_step5',
      family: 'lstm',
      display_name: 'LSTM Autoencoder',
      architecture: {
        hidden_size: 32,
        num_layers: 2,
        latent_dim: 16,
        dropout: 0.1,
      },
      param_count: 28_498,
      best_val_mse: 4.789443077487578e-05,
      best_epoch: 24,
      model_sha256: '3'.repeat(64),
      summary: 'LSTM reconstruction model dengan metrik validasi yang dilaporkan dari training.',
    },
  ],
} satisfies ModelRegistryResponse

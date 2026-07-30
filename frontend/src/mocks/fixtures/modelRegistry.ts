import type {
  ModelRegistryItem,
  ModelRegistryResponse,
} from '../../contracts/modelRegistry'

const sharedFacts: Pick<
  ModelRegistryItem,
  'dataset_reference' | 'window_size' | 'features' | 'score_semantics' | 'report_source'
> = {
  dataset_reference: 'b02f3872_ruang_produksi_v3_march07',
  window_size: 10,
  features: ['suhu', 'rh'],
  score_semantics: 'window_mean_squared_reconstruction_error',
  report_source: 'reported_model_registry',
}

export const modelRegistryResponse = {
  items: [
    {
      ...sharedFacts,
      id: 'conv1d_step5',
      family: 'conv1d',
      display_name: 'Conv1D Autoencoder',
      architecture: { latent_channels: 16 },
      param_count: 7_474,
      best_val_mse: 2.1572509291888413e-05,
      best_epoch: 4,
      model_sha256: '85c901e8fed463207a44151adc14772d3660384ae88daf9fcc53431e6acc39c9',
      summary: 'Conv1D reconstruction model dengan metrik validasi yang dilaporkan dari training.',
    },
    {
      ...sharedFacts,
      id: 'gru_step5',
      family: 'gru',
      display_name: 'GRU Autoencoder',
      architecture: { hidden_size: 32, latent_size: 8, layers: 2, dropout: 0.1 },
      param_count: 20_490,
      best_val_mse: 6.004524724196261e-05,
      best_epoch: 13,
      model_sha256: '0506d1da27d92a259e62c32ce43db7fd19dfa8ad679c08c6d67bf727653a2caa',
      summary: 'GRU reconstruction model dengan metrik validasi yang dilaporkan dari training.',
    },
    {
      ...sharedFacts,
      id: 'lstm_step5',
      family: 'lstm',
      display_name: 'LSTM Autoencoder',
      architecture: { hidden_size: 32, latent_size: 8, layers: 2, dropout: 0.1 },
      param_count: 27_210,
      best_val_mse: 5.146170129209432e-05,
      best_epoch: 24,
      model_sha256: '0dde621c1fe4117fd57602a94c30bd764e900108ceea3675fba6295e9500cccb',
      summary: 'LSTM reconstruction model dengan metrik validasi yang dilaporkan dari training.',
    },
    {
      ...sharedFacts,
      id: 'rnn_step5',
      family: 'rnn',
      display_name: 'RNN Autoencoder',
      architecture: { hidden_size: 32, latent_size: 8, layers: 2, dropout: 0.1 },
      param_count: 7_050,
      best_val_mse: 3.3277092602658214e-05,
      best_epoch: 15,
      model_sha256: 'c801a284c95c16ce9031a24f774d941c314bc0758e7b20d593af64fb630f0ebd',
      summary: 'RNN reconstruction model dengan metrik validasi yang dilaporkan dari training.',
    },
    {
      ...sharedFacts,
      id: 'transformer_step5',
      family: 'transformer',
      display_name: 'Transformer Autoencoder',
      architecture: {
        d_model: 32,
        n_heads: 4,
        encoder_layers: 2,
        decoder_layers: 2,
        ff_dim: 64,
        dropout: 0.1,
      },
      param_count: 43_362,
      best_val_mse: 3.5587262735700976e-05,
      best_epoch: 17,
      model_sha256: '364b0c73be1054b05a33924615d53ee1ebcb12af4bbb7d4efc0c1a144af3e015',
      summary: 'Transformer reconstruction model dengan metrik validasi yang dilaporkan dari training.',
    },
  ],
} satisfies ModelRegistryResponse

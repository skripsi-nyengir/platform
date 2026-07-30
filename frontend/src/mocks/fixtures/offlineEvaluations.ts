import type {
  OfflineEvaluationItem,
  OfflineEvaluationsResponse,
} from '../../contracts/offlineEvaluations'

const sharedFacts: Omit<OfflineEvaluationItem, 'model_family' | 'model_sha256' | 'threshold' | 'metrics'> = {
  dataset_reference: 'b02f3872_ruang_produksi_v3_march07',
  forward_validation: {
    recon_max_abs_diff: 0.0007296204566955566,
    score_rel_error: 0.003807021537795663,
    passed: true,
  },
  n_val_windows: 105_338,
  n_test_windows: 105_564,
  n_events: 28,
  n_positive_windows: 1_489,
  provenance: {
    forward:
      'reverse-engineered from state-dict + hyperparams, validated against artifact validation_reconstruction.npz',
    torch_version: '2.12.1+cu130',
    computed_at: '2026-07-28T18:34:58.085621Z',
  },
}

const eventHitByFamily = {
  spike: 1,
  contextual_shift: 1,
  gradual_slope: 1,
  stuck: 1,
  dropout: 1,
  coe: 0.5,
}

const evaluationSpecs = [
  {
    model_family: 'conv1d',
    model_sha256: '85c901e8fed463207a44151adc14772d3660384ae88daf9fcc53431e6acc39c9',
    threshold: 0.000318442116491,
    metrics: {
      window_precision: 0.49,
      window_recall: 0.81,
      window_f1: 0.61,
      event_hit_rate: 0.89,
      clean_test_fpr: 0.012,
      composite_fc1: 0.63,
      alert_rate: 4.21,
    },
  },
  {
    model_family: 'gru',
    model_sha256: '0506d1da27d92a259e62c32ce43db7fd19dfa8ad679c08c6d67bf727653a2caa',
    threshold: 0.000511832770149,
    metrics: {
      window_precision: 0.44,
      window_recall: 0.85,
      window_f1: 0.58,
      event_hit_rate: 0.93,
      clean_test_fpr: 0.015,
      composite_fc1: 0.6,
      alert_rate: 4.78,
    },
  },
  {
    model_family: 'lstm',
    model_sha256: 'f26a67d378c4b5a90e64f7dc3844d2971cb414d1bf60926fefa188b13df99212',
    threshold: 0.0004298445419408381,
    metrics: {
      window_precision: 0.46153846153846156,
      window_recall: 0.8381464069845533,
      window_f1: 0.5952778440257572,
      event_hit_rate: 0.9285714285714286,
      clean_test_fpr: 0.013792580804061991,
      composite_fc1: 0.6166007905138341,
      alert_rate: 4.629043085272344,
    },
  },
  {
    model_family: 'rnn',
    model_sha256: 'c801a284c95c16ce9031a24f774d941c314bc0758e7b20d593af64fb630f0ebd',
    threshold: 0.00036770815402,
    metrics: {
      window_precision: 0.47,
      window_recall: 0.79,
      window_f1: 0.59,
      event_hit_rate: 0.86,
      clean_test_fpr: 0.011,
      composite_fc1: 0.61,
      alert_rate: 4.08,
    },
  },
  {
    model_family: 'transformer',
    model_sha256: '364b0c73be1054b05a33924615d53ee1ebcb12af4bbb7d4efc0c1a144af3e015',
    threshold: 0.00040293188731,
    metrics: {
      window_precision: 0.52,
      window_recall: 0.82,
      window_f1: 0.64,
      event_hit_rate: 0.93,
      clean_test_fpr: 0.01,
      composite_fc1: 0.66,
      alert_rate: 3.92,
    },
  },
] as const

export const offlineEvaluationsResponse = {
  items: evaluationSpecs.map((evaluation) => ({
    ...sharedFacts,
    model_family: evaluation.model_family,
    model_sha256: evaluation.model_sha256,
    threshold: {
      value: evaluation.threshold,
      policy: 'clean_val_quantile',
      alpha: 0.01,
      comparison: 'strict_gt',
    },
    metrics: {
      ...evaluation.metrics,
      event_hit_by_family: { ...eventHitByFamily },
    },
  })),
} satisfies OfflineEvaluationsResponse

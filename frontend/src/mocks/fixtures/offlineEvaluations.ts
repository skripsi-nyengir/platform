import type {
  OfflineEvaluationItem,
  OfflineEvaluationModelFamily,
  OfflineEvaluationScopeMetrics,
  OfflineEvaluationsResponse,
} from '../../contracts/offlineEvaluations'

type MetricTuple = readonly [
  accuracy: number,
  precision: number,
  recall: number,
  f1: number,
  tn: number,
  fp: number,
  fn: number,
  tp: number,
  nEvaluated: number,
]

interface EvaluationSpec {
  modelFamily: OfflineEvaluationModelFamily
  modelSha256: string
  threshold: number
  timestamp: MetricTuple
  overlappingWindows: MetricTuple
  evaluationBins: MetricTuple
  pointAuc: readonly [roc: number, prTrapezoidal: number]
  provenance: OfflineEvaluationItem['provenance']
}

function scopeMetrics(values: MetricTuple): OfflineEvaluationScopeMetrics {
  const [accuracy, precision, recall, f1, tn, fp, fn, tp, nEvaluated] = values
  return { accuracy, precision, recall, f1, tn, fp, fn, tp, n_evaluated: nEvaluated }
}

function evaluationItem(spec: EvaluationSpec): OfflineEvaluationItem {
  return {
    model_family: spec.modelFamily,
    model_sha256: spec.modelSha256,
    threshold: {
      value: spec.threshold,
      method: 'clean_percentile_99_5',
      percentile: 99.5,
      calibration_split: 'clean_validation',
      comparison: 'strict_gt',
      score_unit: 'timestamp',
      uses_anomaly_labels: false,
      clean_alert_rate: 0.005009107468123861,
    },
    scopes: {
      timestamp: scopeMetrics(spec.timestamp),
      overlapping_model_windows: scopeMetrics(spec.overlappingWindows),
      non_overlapping_evaluation_bins: scopeMetrics(spec.evaluationBins),
    },
    point_auc: {
      roc: spec.pointAuc[0],
      pr_trapezoidal: spec.pointAuc[1],
      pr_definition: 'trapezoidal_precision_recall_auc',
      score_unit: 'timestamp',
    },
    provenance: spec.provenance,
  }
}

const evaluationSpecs: readonly EvaluationSpec[] = [
  {
    modelFamily: 'conv1d',
    modelSha256: '85c901e8fed463207a44151adc14772d3660384ae88daf9fcc53431e6acc39c9',
    threshold: 0.0003201981883103135,
    timestamp: [0.9290281572556163, 0.7199942503952853, 0.47514703092392335, 0.5724898565632321, 92_918, 1_948, 5_533, 5_009, 105_408],
    overlappingWindows: [0.9272266370446325, 0.7605556168007938, 0.5567301484828922, 0.6428737827889857, 90_763, 2_172, 5_493, 6_899, 105_327],
    evaluationBins: [0.9169483341380975, 0.828169014084507, 0.725925925925926, 0.7736842105263158, 1_605, 61, 111, 294, 2_071],
    pointAuc: [0.793323510973309, 0.5783279994006357],
    provenance: {
      metric_authority: 'executed_step7_notebook_output',
      step5_notebook: {
        filename: 'conv1d_autoencoder_b02f3872_ruang_produksi_v3_march07_step5.ipynb',
        sha256: '782c8d9906fe9a6c45e32a1e624e4dabc8c1ce9cc33915608ecd4ba21afb5dbf',
      },
      step7_notebook: {
        filename: 'conv1d_autoencoder_b02f3872_ruang_produksi_v3_march07_step7.ipynb',
        sha256: 'b14aa0b399936b0ce289771a35c0db72d911fcf42cff346776c8d4fbbf16f918',
      },
      artifact_checks: [
        {
          filename: 'conv1d_step5_artifacts.zip',
          sha256: '6698d40f2476343801ab64285ddd9e900e47a2857aa5c090beaf69eda1a30bbf',
          role: 'step5_model_identity',
          consistency: 'matched',
          note: 'Model checkpoint identity and configuration match the Step 5 notebook output.',
        },
      ],
    },
  },
  {
    modelFamily: 'gru',
    modelSha256: '0506d1da27d92a259e62c32ce43db7fd19dfa8ad679c08c6d67bf727653a2caa',
    threshold: 0.0005618056084495022,
    timestamp: [0.9292558439587129, 0.7180828502756963, 0.4817871371656232, 0.5766676128299745, 92_872, 1_994, 5_463, 5_079, 105_408],
    overlappingWindows: [0.9282899921197794, 0.7591858596679164, 0.5719012265978051, 0.6523680213559166, 90_687, 2_248, 5_305, 7_087, 105_327],
    evaluationBins: [0.9237083534524384, 0.8365122615803815, 0.7580246913580246, 0.7953367875647669, 1_606, 60, 98, 307, 2_071],
    pointAuc: [0.7799894501562625, 0.5734345366372323],
    provenance: {
      metric_authority: 'executed_step7_notebook_output',
      step5_notebook: {
        filename: 'gru_autoencoder_b02f3872_ruang_produksi_v3_march07_step5.ipynb',
        sha256: 'ab827505d106df33614ac6f6f3a064a8b99df31e2557a5ce38407e75e734c788',
      },
      step7_notebook: {
        filename: 'gru_autoencoder_b02f3872_ruang_produksi_v3_march07_step7.ipynb',
        sha256: '0b6c47870bc202a9a32bd2fd0e2477c2f985dcc186e3d3aecfdd3a69a309baf3',
      },
      artifact_checks: [],
    },
  },
  {
    modelFamily: 'lstm',
    modelSha256: '0dde621c1fe4117fd57602a94c30bd764e900108ceea3675fba6295e9500cccb',
    threshold: 0.0009487349475675721,
    timestamp: [0.9281648451730419, 0.7487437185929648, 0.42401821286283436, 0.5414244186046512, 93_366, 1_500, 6_072, 4_470, 105_408],
    overlappingWindows: [0.9246536975324465, 0.7895762932154926, 0.4902356358941252, 0.6048989345813004, 91_316, 1_619, 6_317, 6_075, 105_327],
    evaluationBins: [0.9101883148237566, 0.8788927335640139, 0.6271604938271605, 0.7319884726224783, 1_631, 35, 151, 254, 2_071],
    pointAuc: [0.818779816368048, 0.5798428116286538],
    provenance: {
      metric_authority: 'executed_step7_notebook_output',
      step5_notebook: {
        filename: 'lstm_autoencoder_b02f3872_ruang_produksi_v3_march07_step5.ipynb',
        sha256: '17cc1f584a5445c2b986517fd391419c56270ca9ff295df40e46fc2c57bc3ef6',
      },
      step7_notebook: {
        filename: 'lstm_autoencoder_b02f3872_ruang_produksi_v3_march07_step7.ipynb',
        sha256: '70c44870d914617e125997c4defeb360ca813de342c5a8dbf7519af1881a5469',
      },
      artifact_checks: [
        {
          filename: 'lstm_step5_artifacts.zip',
          sha256: 'b05bd9adb10fcc0d6d4eeb5e992fdc5f3f9507b03495067896b7436dd5e0dc27',
          role: 'step5_model_identity',
          consistency: 'matched',
          note: 'Model checkpoint identity and configuration match the Step 5 notebook output.',
        },
      ],
    },
  },
  {
    modelFamily: 'rnn',
    modelSha256: 'c801a284c95c16ce9031a24f774d941c314bc0758e7b20d593af64fb630f0ebd',
    threshold: 0.0005023972923204374,
    timestamp: [0.9293791742562234, 0.7268599882835384, 0.4707835325365206, 0.5714450201496835, 93_001, 1_865, 5_579, 4_963, 105_408],
    overlappingWindows: [0.9282520151528099, 0.7737515570150606, 0.5514041316978696, 0.6439240446685199, 90_937, 1_998, 5_559, 6_833, 105_327],
    evaluationBins: [0.9193626267503622, 0.85, 0.7135802469135802, 0.7758389261744967, 1_615, 51, 116, 289, 2_071],
    pointAuc: [0.830416714497966, 0.6009934335125744],
    provenance: {
      metric_authority: 'executed_step7_notebook_output',
      step5_notebook: {
        filename: 'rnn_autoencoder_b02f3872_ruang_produksi_v3_march07_step5.ipynb',
        sha256: '8e45fd2f21e4ecc8bd3bf7e4cf8dcc3ab8e70427cabbd82c91f3b5995172ce7a',
      },
      step7_notebook: {
        filename: 'rnn_autoencoder_b02f3872_ruang_produksi_v3_march07_step7.ipynb',
        sha256: 'e7a5e21c67e9906bdc2b1843b6753c10fd56fd84f466255f538b02397afe4925',
      },
      artifact_checks: [],
    },
  },
  {
    modelFamily: 'transformer',
    modelSha256: '364b0c73be1054b05a33924615d53ee1ebcb12af4bbb7d4efc0c1a144af3e015',
    threshold: 0.00026567234380490805,
    timestamp: [0.9290945658773527, 0.6989107883817427, 0.5112881806108898, 0.5905554946860961, 92_544, 2_322, 5_152, 5_390, 105_408],
    overlappingWindows: [0.9289356005582614, 0.7389229720518065, 0.6123305358295674, 0.6696968359736993, 90_254, 2_681, 4_804, 7_588, 105_327],
    evaluationBins: [0.9256397875422501, 0.8114143920595533, 0.8074074074074075, 0.8094059405940595, 1_590, 76, 78, 327, 2_071],
    pointAuc: [0.803074512018856, 0.5954529614576256],
    provenance: {
      metric_authority: 'executed_step7_notebook_output',
      step5_notebook: {
        filename: 'transformer_autoencoder_b02f3872_ruang_produksi_v3_march07_step5.ipynb',
        sha256: 'eb199b32d5264c8b94ba394502b429353c2ca5e1fca5dc7b6c1b048e98d6bd43',
      },
      step7_notebook: {
        filename: 'transformer_autoencoder_b02f3872_ruang_produksi_v3_march07_step7.ipynb',
        sha256: 'b0a48d96f920d9178b1cbb1849a0c68d206b66046de7234ed1f4cebbda0894f1',
      },
      artifact_checks: [
        {
          filename: 'transformer_step5_artifacts.zip',
          sha256: 'a7ae8937e9ef97403f63d32cc9be17adc6301d4daa9e5668beb5834c5a99351c',
          role: 'step5_model_identity',
          consistency: 'matched',
          note: 'Model checkpoint identity and configuration match the Step 5 notebook output.',
        },
        {
          filename: 'transformer_step7_artifacts.zip',
          sha256: 'f65c7128f55bdddcbd37d0d63ecde8caa59ba0338997b70d472dee48f6892da8',
          role: 'step7_metric_cross_check',
          consistency: 'conflict',
          note: 'The archive contains a stale selected_operating_threshold.json that conflicts with the executed notebook and its later p99.5 scoring tables; notebook output is authoritative.',
        },
      ],
    },
  },
]

export const offlineEvaluationsResponse = {
  evaluation: {
    dataset_reference: 'b02f3872_ruang_produksi_v3_march07',
    evaluation_split: 'val_injected',
    test_consumed: false,
    primary_scope: 'non_overlapping_evaluation_bins',
    primary_metric: 'f1',
    n_points_total: 105_425,
    n_points_evaluated: 105_408,
    n_model_windows: 105_327,
    n_positive_windows: 12_392,
    n_events: 207,
    evaluation_bin_size_points: 51,
    n_evaluation_bins: 2_071,
    n_skipped_bins: 6,
  },
  items: evaluationSpecs.map(evaluationItem),
} satisfies OfflineEvaluationsResponse

# Anomaly Simulation Demo — Design

Date: 2026-07-29
Status: Validated, not yet implemented

## Goal

Demonstrate the trained anomaly-detection models inside the platform, end to end:

1. Pick a model in the registry.
2. Replay anomalies using the injected dataset.
3. Present the detection results in charts.

The whole platform is a **simulation** of a live IoT pipeline. The data originates
from a real production sensor (B02), but the pipeline that serves it is simulated.
No part of this design uses "production" as a device or registry classifier.

## Evidence base

An offline GPU harness (`/home/reky/college/skripsih/anomaly-sim-harness`) already
validates all three checkpoints against the injected test set. It is the **oracle**
for this feature: the platform must reproduce its numbers, not merely look plausible.

Validation gates already passed:

| Model | Gate A (forward parity) | Gate B (score key) | Corrected threshold |
|---|---:|---|---:|
| LSTM | 7.296204566e-04 | `global_mse` (4.66e-10) | 0.0006799018211 |
| Conv1D | 7.201433182e-04 | `global_mse` (4.66e-10) | 0.000330559548 |
| Transformer | 5.364418030e-07 | `global_mse` (4.66e-10) | 0.0003650374799 |

Detection results on the injected test set (105,238 windows, 210 events):

| Model | Event-hit | Garg Fc1 | Precision | Clean FPR |
|---|---:|---:|---:|---:|
| Transformer | 92.9% | 0.858 | 0.858 | 1.9% |
| Conv1D | 68.6% | 0.689 | 0.749 | 3.0% |
| LSTM | 80.5% | 0.360 | 0.237 | 37.2% |

Two facts that shaped this design:

- Thresholds must come from each artifact's **stored validation scores**, not from
  re-windowing the current `val.npz`. The current val file has 15 segments (7 of them
  smaller than the 30-frame window and therefore dropped); the artifacts were
  calibrated on 3 segments. Re-windowing inflated the LSTM threshold by 89x and made
  it look like it detected nothing.
- The injected test data spans 2026-04-19 → 04-26 WIB, which **overlaps** existing
  B02 telemetry. Storing it under the same `device_id` would violate the
  `telemetry (device_id, ts)` primary key.

## 1. Data and registry

### Device

`devices` currently enforces two constraints that block a second sensor:

- `uq_devices_one_public_active` — unique on `is_active` where `is_active`
- `ck_devices_archive_state` — an inactive device must carry `archived_at`

Marking the simulation sensor as "archived" would be semantically false. Instead:

- Add a `telemetry_kind` column: `historical_replay` | `anomaly_injected`.
- Scope the active-device uniqueness **per kind**, so the injected sensor can be
  active alongside the historical one and appear in the sensor selector.

### Corpus and telemetry

- New `corpora` row `sim_b02_march07_v5_test_injected`, owned by the simulation
  device, interval 2026-04-19 → 04-26 WIB.
- Import 105,767 `telemetry` rows from `test_injected.npz`, **denormalized back to
  physical units** using the archive scaler (min `[24.36616, 18.1394]`,
  max `[30.32931, 68.02039]`), so charts show °C and % rather than 0–1 values.
- `segment_id` derives from the 19 `seg_bounds`; `corpus_index` is sequential;
  `payload_hash` is sha256, matching the existing importer.

### Ground truth

New table `injection_events` holding the 210 injected events (family, severity,
channel, frame index range, timestamp range). Without it a chart can only claim
"the model flagged something" — never "the model was right or wrong".

### Model registry

Three new `model_versions` rows with `runtime_kind='artifact'` (LSTM, Conv1D,
Transformer): corrected thresholds above, `score_key=global_mse`, window 30,
stride 1, `temporal_semantics=context_end`, and `manifest_sha256` set to the real
checkpoint hashes so weights stay traceable.

## 2. Worker GPU inference

### Prerequisite (already completed)

`nvidia-container-toolkit 1.19.1-1` is installed, the `nvidia` docker runtime is
registered, and a container can see the RTX 5050. The platform was restarted and
verified intact afterwards.

### Image

The `torch` cu130 wheels **bundle their own CUDA runtime** — the backend venv runs
GPU forwards with no system CUDA toolkit present. The worker Dockerfile therefore
needs no base-image change, only a torch install from the cu130 index. Image grows
from 239 MB to roughly 3.5 GB.

### Compose

The `worker` service gets an nvidia device reservation
(`driver: nvidia, count: 1, capabilities: [gpu]`).

### Architecture and weights

- Vendor the `nn.Module` classes into the backend: `lstm_autoencoder.py` and
  `conv1d_autoencoder.py` from the archive, plus `transformer_autoencoder.py`
  encoding the reconstructed configuration that passed Gate A at 5.36e-7
  (`batch_first=True`, `norm_first=True`, `gelu`, decoder target = source).
- Weights are **mounted read-only**, not baked into the image, following the
  existing `B02_RAW_ARCHIVE_PATH` pattern via `MODEL_ARTIFACTS_PATH`, and verified
  against `manifest_sha256`.

### Adapter

A new `ArtifactScorer` implements the existing `Scorer` protocol alongside
`PreviewSimulatorScorer`. The two rejection gates — `preview.py:351` and
`service.py:638` — are relaxed **only** for `artifact`, then dispatch on
`runtime_kind`. Results are written with `score_provenance='artifact_inference'`,
distinct from `simulated_preview`, so the UI provenance badge stays honest.

### Invariant

The worker already normalizes windows using the corpus preprocessing snapshot
scaler. Storing the archive scaler on the simulation corpus makes normalization
round-trip exactly back to the injected `[0,1]` values. This is testable, and a
mismatch means something is wrong.

## 3. Chart and presentation

No replay-trigger or model-selection UI exists today. `api/preview.ts` and
`api/modelRegistry.ts` exist but no page drives them. This is genuinely new surface.

### New page `/simulation`

The registry lives on `/model-evaluation` and the charts live on `/sensors/...`.
Forcing the flow into either would split the narrative, so a single page carries
all three steps.

1. **Pick a model** — the three `artifact` rows, each showing its threshold,
   score key, and weight hash. Not a bare dropdown: the reviewer must see which
   model carries which calibration.
2. **Run the replay** — a button issuing `POST /api/replay-jobs` against the
   simulation corpus, then polling status. This machinery already exists and is
   tested; it only lacks a face.
3. **Charts** — four panels sharing one identical time axis:
   - Injected telemetry (°C and %), where anomalies are visible in the signal.
   - Score versus threshold, with points above the threshold marked.
   - **Detection ribbon** — the core request. Two parallel tracks: ground truth
     from `injection_events` against model detections from
     `inference_results.is_anomaly`, colour-coded **TP / FN / FP**. Green means
     caught, red means missed, amber means false alarm.
   - Summary figures: event-hit, precision, recall, FPR.

The ribbon requires a new `/api/injection-events` endpoint so the frontend knows
the truth.

### Model comparison

`inference_results` has primary key `(device_id, score_ts, model_version)`, so all
three models can be replayed over the same window and their ribbons stacked.

## 4. Testing and verification

The offline harness is the oracle. The question is not whether platform numbers look
reasonable, but whether they **match**.

- **Parity test (most critical).** Port Gate A into the backend suite: load
  `validation_reconstruction.npz`, run it through the platform `ArtifactScorer`,
  require max-abs error ≤ 1e-3. If the platform adapter diverges from the harness,
  the test fails rather than silently producing different scores.
- **Normalization round-trip.** Import denormalizes `[0,1]` → physical; the worker
  normalizes physical → `[0,1]`. Assert the round trip returns the original injected
  values within tolerance. This is the silent-failure guard.
- **End-to-end metric regression.** After a replay, assert event-hit and FPR match
  the harness figures within tolerance. This proves the whole chain — import,
  windowing, scaler, threshold, scorer — is intact.
- **Gates stay tight.** Assert that any `runtime_kind` other than
  `preview_simulator` or `artifact` is still rejected in both `preview.py` and
  `service.py`. Two doors are being unlocked, not a wall removed.
- **GPU fails loudly.** Assert a worker without CUDA rejects the job with a clear
  error instead of silently falling back to CPU.
- **Frontend.** Unit tests for TP/FN/FP classification in the ribbon component, an
  e2e test for the three-step flow, and a visual snapshot of the new page. Plus the
  existing gates: lint, 207 unit tests, build, 62 e2e.
- **No regression.** The historical B02 device and the preview simulator path must
  keep working; `test_seed.py` still requires exactly 30 TALPHA rows.

## Risks

- **GPU is a hard dependency.** By explicit choice there is no CPU fallback. On a
  machine without `nvidia-container-toolkit`, the worker will stop rather than run
  slowly. Measured cost of that choice: CPU inference over all 105,238 windows takes
  1.8 s for one model and 5.4 s for all three, so the GPU requirement is a
  presentation decision rather than a performance one.
- **Threshold provenance.** Thresholds derive from the parent dataset variant
  (`march07_revised`) windowing while the test set is `march07_v5`. The LSTM's 37.2%
  false-positive rate is most likely a symptom of that threshold failing to transfer,
  not simply a weak model. This limitation belongs in the thesis write-up.
- **Image size.** The worker image grows roughly fifteen-fold, which affects build
  and deploy time.

# TALPHA Dataset UI Adaptation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the legacy six-device frontend dataset with the canonical two-node TALPHA validation corpus while preserving the existing shell, six routes, page hierarchy, dark theme, interactions, accessibility, and desktop responsiveness.

**Architecture:** Canonical sibling-repository data is read only during offline fixture preparation. Inverse-scaled, deterministic TALPHA data is checked into the existing fixture modules and continues through the current MSW, typed API, React Query, page, component, and test seams. No runtime import, filesystem read, symlink, Vite alias, backend, or generic dataset layer is introduced.

**Tech Stack:** React 19, TypeScript 6, Zod 4, MUI 9, MUI X Charts/Data Grid, React Query 5, MSW 2, Vitest 4, Testing Library, Playwright 1.61, Vite 8.

## Global Constraints

- Work only under `/home/reky/college/skripsih/anomaly-detection-platform/frontend`.
- Treat `/home/reky/college/skripsih/anomaly-detection` as read-only.
- Do not modify `docs/superpowers/plans/2026-07-21-backend-serving-persistence.md`.
- Do not read `test.npz` or display test-split evidence.
- Do not add dependencies, routes, pages, services, adapters, aliases, compatibility mappings, or dataset selectors.
- Preserve `/`, `/sensors/:sensorId`, `/alerts`, `/eda`, `/model-evaluation`, and `/system-health`.
- Accept only `talpha-1` and `talpha-2`.
- Display only `TALPHA-1` and `TALPHA-2`.
- Use `temperature_c` and `relative_humidity_pct`.
- Preserve source timestamp spacing and gaps.
- Never append `Z` to TALPHA fixture timestamps or label them UTC.
- Show `Zona waktu tidak diketahui` beside every TALPHA time context.
- Use exact copy where applicable: `Data fixture historis`, `Deteksi ambang model, bukan ground truth`, and `Bukan status deployment langsung`.
- Derive every `is_anomaly` value as strict `score > threshold`.
- Preserve alert acknowledgement-before-resolution, retries, idempotency, retained state, polling errors, skeletons, empty states, bounded tables, request IDs, and partial-panel isolation.
- Keep all labeled evaluation structures hidden for all seven tracks.
- Preserve existing keyboard focus, semantic headings, chart ARIA summaries, `Lihat data`, desktop breakpoints, and no-horizontal-overflow behavior.
- Do not add mobile navigation or redesign any surface.

---

## Ultrawork Execution Graph

| Wave | Tasks | Worker Category | Dependency |
|---|---|---|---|
| 1 | Task 1 | `deep` | None |
| 2 | Tasks 2 and 3 in parallel | `deep` | Task 1 |
| 3 | Task 4 | `deep` | Tasks 2 and 3 |
| 4 | Tasks 5, 6, 7, 8, and 9 in parallel | `visual-engineering` | Task 4 |
| 5 | Task 10 | `visual-engineering` with `playwright` and `visual-qa` | Tasks 5–9 |
| 6 | Task 11 | `unspecified-high` verifier | Task 10 |

## Shared-File Ownership

| File | Sole Owning Task |
|---|---|
| `src/contracts/contracts.test.ts` | Tasks 1 then 3, sequentially |
| `src/mocks/handlers.test.ts` | Tasks 2 then 4, sequentially |
| `src/components/filters/TemporalFilterBar.tsx` | Task 1 |
| `src/components/charts/temporalOptions.ts` | Task 1 |
| `src/app/navigation.ts` | Task 1 |
| `playwright.config.ts` | Task 10 |
| `tests/e2e/helpers.ts` | Task 10 |
| `tests/production/verify-dist.test.mjs` | Task 10 |

---

### Task 1: Establish TALPHA Identity, Time, Navigation, And Contract Boundaries

**Depends on:** None

**Unblocks:** Tasks 2 and 3

**Files:**

- Modify: `frontend/src/contracts/common.ts`
- Modify: `frontend/src/contracts/telemetry.ts`
- Modify: `frontend/src/contracts/inference.ts`
- Modify: `frontend/src/contracts/alerts.ts`
- Modify: `frontend/src/contracts/eda.ts`
- Modify: `frontend/src/contracts/modelEvaluation.ts`
- Modify: `frontend/src/contracts/systemHealth.ts`
- Modify: `frontend/src/contracts/contracts.test.ts`
- Modify: `frontend/src/features/filters/urlFilters.ts`
- Modify: `frontend/src/features/filters/urlFilters.test.ts`
- Modify: `frontend/src/components/filters/TemporalFilterBar.tsx`
- Modify: `frontend/src/components/filters/TemporalFilterBar.test.tsx`
- Modify: `frontend/src/components/charts/temporalOptions.ts`
- Modify: `frontend/src/components/charts/options.test.ts`
- Modify: `frontend/src/app/navigation.ts`
- Modify: `frontend/src/app/routes.test.tsx`
- Modify: `frontend/src/features/alerts/alertCommand.ts`
- Modify: `frontend/src/features/alerts/lifecycle.test.tsx`

**Interfaces:**

```ts
export const sensorIds = ['talpha-1', 'talpha-2'] as const
export const SensorIdSchema = z.enum(sensorIds)
export type SensorId = z.infer<typeof SensorIdSchema>

export const sensorLabels: Readonly<Record<SensorId, string>> = Object.freeze({
  'talpha-1': 'TALPHA-1',
  'talpha-2': 'TALPHA-2',
})

export const HistoricalDateTimeSchema = z
  .string()
  .regex(
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/,
    'historical timestamps must not contain a timezone offset',
  )
  .pipe(z.iso.datetime({ local: true, precision: 0 }))

export type HistoricalDateTime = z.infer<typeof HistoricalDateTimeSchema>

export function compareHistoricalDateTimes(left: string, right: string): number

export function historicalDateTimeToDate(value: string): Date

export function dateToHistoricalDateTime(value: Date): string
```

**Exact implementations:**

```ts
export function compareHistoricalDateTimes(left: string, right: string): number {
  return left.localeCompare(right)
}

export function historicalDateTimeToDate(value: string): Date {
  const parsed = HistoricalDateTimeSchema.parse(value)
  const [datePart, timePart] = parsed.split('T') as [string, string]
  const [year, month, day] = datePart.split('-').map(Number) as [number, number, number]
  const [hour, minute, second] = timePart.split(':').map(Number) as [
    number,
    number,
    number,
  ]

  return new Date(year, month - 1, day, hour, minute, second)
}

export function dateToHistoricalDateTime(value: Date): string {
  return value.toISOString().slice(0, 19)
}
```

```ts
export const talphaValidationRange = Object.freeze({
  from: '2025-12-11T23:50:35',
  to: '2025-12-18T07:52:42',
})
```

**Model-evaluation additions:**

```ts
export const ThresholdPolicySchema = z.strictObject({
  source_split: z.literal('val'),
  percentile: z.literal(99.5),
  comparison: z.literal('>'),
})

export const ValidationTrackFieldsSchema = z.strictObject({
  version: z.string().min(1),
  model: z.string().min(1),
  track: z.string().min(1),
  label: z.string().min(1),
  score_key: z.string().min(1),
  score_semantics: z.string().min(1),
  evaluation_period: z.string().min(1),
  validation_only: z.literal(true),
  test_evaluated: z.literal(false),
  n_val_windows: z.number().int().positive(),
  threshold: z.number(),
  threshold_policy: ThresholdPolicySchema,
  has_labeled_ground_truth: z.boolean(),
  available_metrics: z.array(z.string().min(1)).max(500),
  summary: z.string().min(1),
})
```

`ModelEvaluationDetailSchema` must contain the same track fields plus the existing request ID, numeric metrics, optional labeled structures, nullable hash fields, and notes. Remove `created_at` because `comparison_summary.json` does not provide an artifact creation time.

**Alert provenance additions:**

```ts
export const DetectionBasisSchema = z.literal('threshold_model_fixture')

export const ScoreProvenanceSchema = z.literal('deterministic_threshold_fixture')
```

Add `detection_basis: DetectionBasisSchema` to `AlertEventSchema` and `CurrentAlertSchema`.

Add `score_provenance: ScoreProvenanceSchema` to `InferencePointSchema`.

Remove `model_hash`, `preprocessing_hash`, and `threshold_hash` from `InferencePointSchema`; the approved sources do not provide real score-array artifact hashes.

**Contract limits:**

```ts
sensors: z.array(LatestTelemetrySensorSchema).max(2)
device_ids: z.array(SensorIdSchema).max(2)
sensor_comparison: z.array(SensorComparisonSchema).max(2)
fresh_sensor_count: z.number().int().min(0).max(2)
stale_sensor_count: z.number().int().min(0).max(2)
offline_sensor_count: z.number().int().min(0).max(2)
```

The system telemetry sum refinement must reject totals greater than two.

**Historical timestamp fields:**

- `AlertCommandRequestSchema.event_ts`
- `LatestTelemetrySensorSchema.ts`
- `LatestTelemetryResponseSchema.generated_at`
- `TelemetryPointSchema.ts`
- Telemetry query and response `from`/`to`
- Inference query `from`/`to`
- Inference window start/end
- Alert event and current-alert timestamps
- Alert-event query `from`/`to`
- Current-alert response `generated_at`
- EDA query/scope/candidate/correlation timestamps
- System status/service/latest telemetry timestamps
- Mock liveness/readiness timestamps

- [ ] **Step 1: Add failing identity and timestamp tests**

Add to `frontend/src/contracts/contracts.test.ts`:

```ts
it('accepts only TALPHA IDs and no-offset historical timestamps', () => {
  expect(sensorIds).toEqual(['talpha-1', 'talpha-2'])
  expect(SensorIdSchema.parse('talpha-1')).toBe('talpha-1')
  expect(SensorIdSchema.parse('talpha-2')).toBe('talpha-2')
  expect(sensorLabels).toEqual({
    'talpha-1': 'TALPHA-1',
    'talpha-2': 'TALPHA-2',
  })

  for (const legacyId of ['n1', 'n2', 'n3', 'n4', 'n5', 'n6']) {
    expect(SensorIdSchema.safeParse(legacyId).success).toBe(false)
  }

  expect(HistoricalDateTimeSchema.parse('2025-12-11T23:50:35')).toBe(
    '2025-12-11T23:50:35',
  )
  expect(HistoricalDateTimeSchema.safeParse('2025-12-11T23:50:35Z').success).toBe(false)
  expect(
    HistoricalDateTimeSchema.safeParse('2025-12-11T23:50:35+07:00').success,
  ).toBe(false)
})
```

- [ ] **Step 2: Run the identity test and confirm failure**

Run from `frontend`:

```bash
npm test -- src/contracts/contracts.test.ts
```

Expected: FAIL because TALPHA exports do not exist, `talpha-1` is rejected, and no-offset timestamps are rejected.

- [ ] **Step 3: Implement the shared identity and historical-time interfaces**

Update `common.ts` with the exact exports and function signatures above. Replace every `Rfc3339Schema` import with `HistoricalDateTimeSchema` for historical fixture fields.

- [ ] **Step 4: Replace direct historical timestamp comparisons**

Replace contract and handler-facing `Date.parse(left) < Date.parse(right)` checks with:

```ts
compareHistoricalDateTimes(left, right) < 0
```

Replace equality/range variants with the corresponding `<=`, `>=`, or `>` comparison against zero.

- [ ] **Step 5: Replace chart-side historical date construction**

In `temporalOptions.ts`, `SensorHistoryPanel.tsx`, and `TemporalPatternsPanel.tsx`, historical chart dates must be constructed with:

```ts
historicalDateTimeToDate(timestamp)
```

Do not use `new Date(timestamp)` for TALPHA fixture timestamps.

- [ ] **Step 6: Add failing filter and navigation tests**

Add assertions that:

```ts
expect(parseUrlFilters(new URLSearchParams())).toMatchObject({
  from: '2025-12-11T23:50:35',
  to: '2025-12-18T07:52:42',
  bucket: '15m',
})

expect(navigationItems.find(({ label }) => label === 'Sensors')?.path).toBe(
  '/sensors/talpha-1',
)
```

Assert all six legacy route IDs redirect to `/`.

- [ ] **Step 7: Run filter and route tests and confirm failure**

```bash
npm test -- src/features/filters/urlFilters.test.ts src/app/routes.test.tsx src/components/filters/TemporalFilterBar.test.tsx
```

Expected: FAIL with the old 2026 defaults, `/sensors/n1`, and six legacy selector values.

- [ ] **Step 8: Implement TALPHA defaults and selectors**

Use `talphaValidationRange` as the sole URL-filter default. Render options as:

```tsx
<option key={sensorId} value={sensorId}>
  {sensorLabels[sensorId]}
</option>
```

Change the navigation path union and Sensors item to `/sensors/talpha-1`.

- [ ] **Step 9: Make fixture lifecycle command times offset-free**

Update `createAlertLifecycleCommand` without changing its public signature:

```ts
export function createAlertLifecycleCommand(
  alertId: string,
  action: 'acknowledge' | 'resolve',
  note?: string,
): AlertLifecycleCommand
```

Generate `event_ts` with:

```ts
event_ts: dateToHistoricalDateTime(new Date())
```

- [ ] **Step 10: Complete model-evaluation contract migration**

Add the exact validation-track fields. Preserve the existing refinement that rejects labeled structures when `has_labeled_ground_truth` is false.

- [ ] **Step 11: Run the complete Task 1 test set**

```bash
npm test -- src/contracts/contracts.test.ts src/features/filters/urlFilters.test.ts src/components/filters/TemporalFilterBar.test.tsx src/components/charts/options.test.ts src/app/routes.test.tsx src/features/alerts/lifecycle.test.tsx
```

Expected: PASS. The only accepted IDs are the two TALPHA IDs, local historical timestamps parse, offset-bearing fixture timestamps fail, default dates are 2025 TALPHA dates, and route behavior remains unchanged except for the canonical sensor destination.

---

### Task 2: Prepare Canonical Telemetry, Arm B Score, And Alert Fixtures

**Depends on:** Task 1

**Unblocks:** Task 4

**Files:**

- Modify: `frontend/src/mocks/fixtures/telemetry.ts`
- Modify: `frontend/src/mocks/fixtures/inference.ts`
- Modify: `frontend/src/mocks/fixtures/alerts.ts`
- Modify: `frontend/src/mocks/state.ts`
- Modify: `frontend/src/mocks/handlers.test.ts`

**Canonical sources:**

```text
/home/reky/college/skripsih/anomaly-detection/data/processed/talpha/metadata.json
/home/reky/college/skripsih/anomaly-detection/data/processed/talpha/val.npz
/home/reky/college/skripsih/anomaly-detection/configs/conv1d_talpha.yaml
/home/reky/college/skripsih/anomaly-detection/runs/benchmark_validation_figures/comparison/comparison_summary.json
```

**Interfaces:**

```ts
export const fixtureGeneratedAt = '2025-12-18T07:52:42'

export const armBThresholds: Readonly<Record<SensorId, number>>

export const latestTelemetrySensors: readonly LatestTelemetrySensor[]

export const telemetryHistoryBySensor: Readonly<
  Record<SensorId, readonly TelemetryPoint[]>
>

export const dataGapTelemetryHistoryBySensor: Readonly<
  Record<SensorId, readonly TelemetryPoint[]>
>

export const normalInferenceBySensor: Readonly<
  Record<SensorId, readonly InferencePoint[]>
>

export const activeAnomalyInferenceBySensor: Readonly<
  Record<SensorId, readonly InferencePoint[]>
>
```

**Exact thresholds:**

```ts
export const armBThresholds = Object.freeze({
  'talpha-1': 0.02707822278141974,
  'talpha-2': 0.031537856459617604,
} satisfies Record<SensorId, number>)
```

**Channel mapping:**

```text
talpha-1: values[:, 0] -> temperature_c; values[:, 1] -> relative_humidity_pct
talpha-2: values[:, 2] -> temperature_c; values[:, 3] -> relative_humidity_pct
```

**Inverse scaling:**

```py
physical_values = scaled_values * (scaler_maximum - scaler_minimum) + scaler_minimum
```

**Normal telemetry indices:**

```text
0, 1, 2, 3, 4, 5
```

**Gap telemetry indices:**

```text
36030, 36031, 36032, 36033, 65144, 65145, 65146, 65147
```

Set `gap_before: true` only for indices `36032` and `65146`.

**Latest telemetry index:**

```text
86103
```

**Latest physical values:**

```text
TALPHA-1: temperature_c 24.6772; relative_humidity_pct 54.7147
TALPHA-2: temperature_c 21.2452; relative_humidity_pct 45.7578
```

**Inference windows:**

```text
start index 0, end index 29
start index 30, end index 59
start index 60, end index 89
start index 90, end index 119
```

**Deterministic score values:**

```ts
'talpha-1': [
  0.013,
  0.019,
  0.02707822278141974,
  0.021,
]

'talpha-2': [
  0.014,
  0.022,
  0.031537856459617604,
  0.025,
]
```

For the active-anomaly scenario, replace the last `talpha-1` score with `0.028`.

**Inference helper:**

```ts
function inferencePoint(
  deviceId: SensorId,
  windowStart: string,
  windowEnd: string,
  score: number,
): Readonly<InferencePoint>
```

Its return value must contain:

```ts
{
  window_start_ts: windowStart,
  window_end_ts: windowEnd,
  score,
  threshold: armBThresholds[deviceId],
  is_anomaly: score > armBThresholds[deviceId],
  model_version: `conv1d-arm-b-${deviceId}-validation-fixture`,
  score_provenance: 'deterministic_threshold_fixture',
}
```

**Alert fixture identity:**

```text
alert_id: alert_talpha_1_active
event_id: event_talpha_1_detected
device_id: talpha-1
actor: threshold-model-fixture
score: 0.028
threshold: 0.02707822278141974
detection_basis: threshold_model_fixture
```

- [ ] **Step 1: Add failing source-mapping and threshold tests**

Add to `handlers.test.ts` before replacing fixtures:

```ts
it('serves only the two canonical TALPHA latest readings', async () => {
  const response = LatestTelemetryResponseSchema.parse(
    await (await apiFetch('/api/telemetry/latest')).json(),
  )

  expect(response.sensors.map(({ device_id }) => device_id)).toEqual([
    'talpha-1',
    'talpha-2',
  ])
  expect(response.sensors).toEqual([
    expect.objectContaining({
      device_id: 'talpha-1',
      ts: '2025-12-18T07:52:42',
      temperature_c: 24.6772,
      relative_humidity_pct: 54.7147,
    }),
    expect.objectContaining({
      device_id: 'talpha-2',
      ts: '2025-12-18T07:52:42',
      temperature_c: 21.2452,
      relative_humidity_pct: 45.7578,
    }),
  ])
})
```

```ts
it('uses exact Arm B thresholds and strict exceedance', async () => {
  setMockScenario('normal')

  const first = InferenceResponseSchema.parse(
    await (
      await apiFetch(
        '/api/inference-results?device_id=talpha-1&from=2025-12-11T23%3A50%3A35&to=2025-12-18T07%3A52%3A42&limit=10',
      )
    ).json(),
  )

  expect(first.points.find(({ score, threshold }) => score === threshold)).toMatchObject({
    threshold: 0.02707822278141974,
    is_anomaly: false,
  })

  setMockScenario('active-anomaly')

  const active = InferenceResponseSchema.parse(
    await (
      await apiFetch(
        '/api/inference-results?device_id=talpha-1&from=2025-12-11T23%3A50%3A35&to=2025-12-18T07%3A52%3A42&limit=10',
      )
    ).json(),
  )

  expect(active.points.at(-1)).toMatchObject({
    score: 0.028,
    threshold: 0.02707822278141974,
    is_anomaly: true,
    score_provenance: 'deterministic_threshold_fixture',
  })
})
```

- [ ] **Step 2: Run the fixture-facing tests and confirm failure**

```bash
npm test -- src/mocks/handlers.test.ts
```

Expected: FAIL because handlers still return six legacy devices, 2026 timestamps, shared telemetry histories, threshold `0.8`, and legacy alert IDs.

- [ ] **Step 3: Extract canonical fixture values read-only**

Run from `frontend`:

```bash
python - <<'PY'
from datetime import datetime, timezone
from pathlib import Path
import json
import numpy as np

root = Path("/home/reky/college/skripsih/anomaly-detection")
metadata = json.loads((root / "data/processed/talpha/metadata.json").read_text())
with np.load(root / "data/processed/talpha/val.npz") as data:
    scaled = data["values"].astype(np.float64)
    timestamps = data["timestamps"]
    segment_bounds = data["seg_bounds"]

minimum = np.asarray(metadata["scaler"]["min"], dtype=np.float64)
maximum = np.asarray(metadata["scaler"]["max"], dtype=np.float64)
physical = scaled * (maximum - minimum) + minimum

normal_indices = [0, 1, 2, 3, 4, 5]
gap_indices = [36030, 36031, 36032, 36033, 65144, 65145, 65146, 65147]
latest_index = 86103
window_indices = [(0, 29), (30, 59), (60, 89), (90, 119)]

def timestamp(index):
    return datetime.fromtimestamp(
        int(timestamps[index]),
        timezone.utc,
    ).strftime("%Y-%m-%dT%H:%M:%S")

def row(index):
    return {
        "index": index,
        "ts": timestamp(index),
        "talpha-1": {
            "temperature_c": round(float(physical[index, 0]), 4),
            "relative_humidity_pct": round(float(physical[index, 1]), 4),
        },
        "talpha-2": {
            "temperature_c": round(float(physical[index, 2]), 4),
            "relative_humidity_pct": round(float(physical[index, 3]), 4),
        },
    }

print(json.dumps({
    "segment_bounds": segment_bounds.tolist(),
    "normal": [row(index) for index in normal_indices],
    "gaps": [row(index) for index in gap_indices],
    "latest": row(latest_index),
    "windows": [
        {"start": timestamp(start), "end": timestamp(end)}
        for start, end in window_indices
    ],
}, indent=2))
PY
```

Expected: JSON containing only validation-derived data, no timezone suffixes, segment bounds `[0, 36032, 65146, 86104]`, and the latest physical values listed above.

- [ ] **Step 4: Replace telemetry fixtures**

Create per-node histories from the exact extraction output. Set raw `sample_count: 1`. Never derive x-axis position from array index.

- [ ] **Step 5: Replace inference fixtures**

Implement the exact threshold map and helper. Do not pass `is_anomaly` into the helper; derive it inside the helper.

- [ ] **Step 6: Replace alert fixtures and state seeds**

Seed active-anomaly state only with the new TALPHA-1 detection. Keep fixture objects frozen and clone them through the existing state-reset path.

- [ ] **Step 7: Update stale and offline fixtures**

Use `talpha-2` for both named scenarios. Keep the scenarios separate. Use no-offset validation timestamps and total system counts of two.

- [ ] **Step 8: Run Task 2 tests**

```bash
npm test -- src/mocks/handlers.test.ts src/features/alerts/lifecycle.test.tsx
```

Expected: PASS for canonical source mapping, strict threshold equality, active anomaly, frozen state reset, and retained lifecycle ordering.

---

### Task 3: Prepare Canonical EDA, Seven Evaluation Tracks, And Historical Health Fixtures

**Depends on:** Task 1

**Unblocks:** Task 4

**Files:**

- Modify: `frontend/src/mocks/fixtures/eda.ts`
- Modify: `frontend/src/mocks/fixtures/modelEvaluations.ts`
- Modify: `frontend/src/mocks/fixtures/systemHealth.ts`
- Modify: `frontend/src/contracts/contracts.test.ts`

**Canonical EDA facts:**

```ts
export const talphaValidationFacts = Object.freeze({
  validation_rows_per_node: 86_104,
  combined_observations: 172_208,
  max_gap_seconds: 600,
  gap_count: 2,
  gap_seconds: [5_585, 2_609],
  cadence_seconds: {
    minimum: 1,
    median: 6,
    p95: 8,
    maximum_without_gap: 587,
  },
})
```

**Per-node statistics:**

| Node | Temperature Mean | Temperature P05 | Temperature P95 | RH Mean | RH P05 | RH P95 | Temp/RH Correlation |
|---|---:|---:|---:|---:|---:|---:|---:|
| TALPHA-1 | 25.290310 | 24.612841 | 26.210880 | 49.025707 | 39.722961 | 56.446591 | 0.18012467 |
| TALPHA-2 | 21.535726 | 20.859051 | 22.156790 | 46.498052 | 40.737671 | 52.380131 | 0.73702280 |

Combined correlation: `0.33088276`.

**Seven evaluation tracks:**

| Version Key | Label | Model | Track | Score Key | Threshold |
|---|---|---|---|---|---:|
| `ewma-canonical-4ch` | `EWMA` | `ewma` | `canonical_4ch` | `global_mae` | `0.047478773146867714` |
| `pca-canonical-4ch` | `PCA` | `pca` | `canonical_4ch` | `global_mae` | `0.057222952693700785` |
| `conv1d-arm-a` | `Conv1D Arm A` | `conv1d_autoencoder` | `arm_a` | `global_mae` | `0.025718613043427447` |
| `conv1d-arm-b-talpha1` | `Conv1D Arm B · TALPHA-1` | `conv1d_autoencoder` | `arm_b_talpha1` | `global_mae` | `0.02707822278141974` |
| `conv1d-arm-b-talpha2` | `Conv1D Arm B · TALPHA-2` | `conv1d_autoencoder` | `arm_b_talpha2` | `global_mae` | `0.031537856459617604` |
| `tranad-canonical-4ch` | `TranAD` | `tranad` | `canonical_4ch` | `averaged_global_mse` | `0.007528403326869005` |
| `usad-canonical-4ch` | `USAD` | `usad` | `canonical_4ch` | `averaged_global_mse` | `0.008044914752244947` |

**Shared evaluation values:**

```ts
{
  evaluation_period: '2025-12-11T23:50:35 – 2025-12-18T07:52:42',
  validation_only: true,
  test_evaluated: false,
  n_val_windows: 86_017,
  threshold_policy: {
    source_split: 'val',
    percentile: 99.5,
    comparison: '>',
  },
  has_labeled_ground_truth: false,
  strict_exceedance_count: 431,
  strict_exceedance_fraction: 0.005010637432135508,
  available_metrics: [
    'threshold',
    'strict_exceedance_count',
    'strict_exceedance_fraction',
  ],
}
```

**Score semantics:**

```text
EWMA, PCA, Conv1D:
global mean absolute reconstruction error (MAE)

TranAD, USAD:
average of two global mean squared reconstruction errors (MSE)
```

**Required disclaimer:**

```text
This validation-only calibration summary does not measure anomaly-detection accuracy. Raw reconstruction magnitudes use different MAE/MSE semantics and are not compared directly.
```

- [ ] **Step 1: Add failing fixture-schema tests**

Add to `contracts.test.ts`:

```ts
it('parses exactly seven unlabeled validation-only tracks', () => {
  expect(modelEvaluationSummaries).toHaveLength(7)

  for (const summary of modelEvaluationSummaries) {
    expect(ModelEvaluationSummarySchema.parse(summary)).toMatchObject({
      validation_only: true,
      test_evaluated: false,
      n_val_windows: 86_017,
      has_labeled_ground_truth: false,
      threshold_policy: {
        source_split: 'val',
        percentile: 99.5,
        comparison: '>',
      },
    })
  }

  for (const detail of Object.values(modelEvaluationDetails)) {
    const parsed = ModelEvaluationDetailSchema.parse(detail)
    expect(parsed.confusion_matrix).toBeUndefined()
    expect(parsed.roc).toBeUndefined()
    expect(parsed.precision_recall).toBeUndefined()
  }
})
```

```ts
it('keeps TALPHA EDA and health fixture collections bounded to two nodes', () => {
  expect(edaSensorComparisons.map(({ device_id }) => device_id)).toEqual([
    'talpha-1',
    'talpha-2',
  ])
  expect(systemStatus.telemetry).toMatchObject({
    fresh_sensor_count: 2,
    stale_sensor_count: 0,
    offline_sensor_count: 0,
  })
})
```

- [ ] **Step 2: Run the fixture-schema tests and confirm failure**

```bash
npm test -- src/contracts/contracts.test.ts
```

Expected: FAIL because evaluation fixtures still contain two labeled production candidates, EDA contains six legacy rows, and health reports six live sensors.

- [ ] **Step 3: Replace EDA fixtures**

Set exactly two sensor-comparison rows. Use `sample_count: 86_104` per node and `coverage_pct: 100`.

Extend `CoverageSummarySchema` with:

```ts
cadence_seconds: z.strictObject({
  minimum: z.number().nonnegative(),
  median: z.number().nonnegative(),
  p95: z.number().nonnegative(),
  maximum_without_gap: z.number().nonnegative(),
  gap_threshold: z.number().positive(),
})
```

Populate it with:

```ts
{
  minimum: 1,
  median: 6,
  p95: 8,
  maximum_without_gap: 587,
  gap_threshold: 600,
}
```

- [ ] **Step 4: Replace model-evaluation fixtures**

Create exactly seven summary and detail records. Set `metrics` to:

```ts
{
  threshold: track.threshold,
  strict_exceedance_count: 431,
  strict_exceedance_fraction: 0.005010637432135508,
}
```

Set model, preprocessing, and threshold hashes to `null`. Do not invent a creation time.

- [ ] **Step 5: Replace system-health fixture semantics**

Use:

```ts
overall_observation:
  'Data fixture historis; bukan status deployment langsung'

services: [
  {
    name: 'api',
    liveness: 'unknown',
    readiness: 'unknown',
    checked_at: fixtureGeneratedAt,
    detail: 'Status deployment tidak dievaluasi oleh fixture historis',
  },
  {
    name: 'database',
    liveness: 'unknown',
    readiness: 'unknown',
    checked_at: fixtureGeneratedAt,
    detail: 'Koneksi database langsung tidak dievaluasi',
  },
  {
    name: 'inference-worker',
    liveness: 'unknown',
    readiness: 'unknown',
    checked_at: fixtureGeneratedAt,
    detail: 'Tidak ada bukti worker langsung; skor adalah fixture deterministik',
  },
]
```

Keep `/health` and `/ready` response contracts intact for API compatibility, but do not use them as evidence on the System Health page.

- [ ] **Step 6: Run Task 3 tests**

```bash
npm test -- src/contracts/contracts.test.ts
```

Expected: PASS with seven schema-valid validation-only tracks, two EDA rows, no labeled structures, null artifact hashes, historical health wording, and two-node totals.

---

### Task 4: Integrate TALPHA Fixtures Through Existing MSW Routes And Scenarios

**Depends on:** Tasks 2 and 3

**Unblocks:** Tasks 5–9

**Files:**

- Modify: `frontend/src/mocks/handlers.ts`
- Modify: `frontend/src/mocks/scenario.ts` only if fixture copy requires it
- Modify: `frontend/src/mocks/handlers.test.ts`
- Modify: `frontend/src/api/api.test.ts`
- Modify: `frontend/src/test/task4QueryHooks.test.tsx`
- Modify: `frontend/src/features/telemetry/queries.test.tsx`
- Modify: `frontend/src/features/inference/queries.test.tsx`
- Modify: `frontend/src/features/eda/queries.test.tsx`
- Modify: `frontend/src/features/systemHealth/query.test.tsx`

**Scenario assignment:**

```ts
const scenarioDevice = {
  'active-anomaly': 'talpha-1',
  stale: 'talpha-2',
  offline: 'talpha-2',
  'data-gap': 'talpha-2',
  empty: 'talpha-2',
} as const
```

**EDA response calculations:**

```ts
const selectedNodeCount = deviceId === undefined ? 2 : 1
const expectedCount = 86_104 * selectedNodeCount
const observedCount = expectedCount
const gapCount = empty ? 0 : 2
```

**Correlation values:**

```ts
const correlationByScope = {
  all: 0.33088276,
  'talpha-1': 0.18012467,
  'talpha-2': 0.7370228,
} as const
```

- [ ] **Step 1: Replace handler matrix expectations before implementation**

Update every normal endpoint test to use:

```ts
const from = '2025-12-11T23:50:35'
const to = '2025-12-18T07:52:42'
```

Use encoded query parameters via `URLSearchParams`, not hand-written `Z` timestamps.

- [ ] **Step 2: Add failing rejection tests for every legacy ID**

```ts
it.each(['n1', 'n2', 'n3', 'n4', 'n5', 'n6'])(
  'returns 422 for retired sensor %s',
  async (legacyId) => {
    const response = await apiFetch(
      `/api/telemetry/latest?device_id=${encodeURIComponent(legacyId)}`,
    )

    expect(response.status).toBe(422)
    expect(ProblemDetailsSchema.parse(await response.json())).toMatchObject({
      status: 422,
      request_id: 'req_invalid_query',
    })
  },
)
```

Repeat coverage through telemetry history, inference, alerts, and EDA by using the shared `SensorIdSchema` boundary rather than adding compatibility logic.

- [ ] **Step 3: Add failing gap and EDA tests**

```ts
it('marks both canonical validation gaps from timestamp and segment boundaries', async () => {
  setMockScenario('data-gap')

  const history = TelemetryHistoryResponseSchema.parse(
    await (
      await apiFetch(
        `/api/telemetry/history?${new URLSearchParams({
          device_id: 'talpha-2',
          from,
          to,
          bucket: 'raw',
          limit: '20',
        })}`,
      )
    ).json(),
  )

  expect(history.points.filter(({ gap_before }) => gap_before)).toEqual([
    expect.objectContaining({ ts: '2025-12-14T15:57:48' }),
    expect.objectContaining({ ts: '2025-12-16T19:26:21' }),
  ])
})
```

```ts
it('reports validation-derived EDA counts, cadence, and correlations', async () => {
  const summary = EdaSummaryResponseSchema.parse(
    await (
      await apiFetch(
        `/api/eda/summary?${new URLSearchParams({ from, to, bucket: 'raw' })}`,
      )
    ).json(),
  )

  expect(summary.coverage).toEqual({
    expected_count: 172_208,
    observed_count: 172_208,
    coverage_pct: 100,
    gap_count: 2,
    cadence_seconds: {
      minimum: 1,
      median: 6,
      p95: 8,
      maximum_without_gap: 587,
      gap_threshold: 600,
    },
  })
})
```

- [ ] **Step 4: Run handler tests and confirm failure**

```bash
npm test -- src/mocks/handlers.test.ts src/api/api.test.ts src/test/task4QueryHooks.test.tsx
```

Expected: FAIL on legacy IDs, dates, counts, shared histories, active-alert identity, and old model-evaluation totals.

- [ ] **Step 5: Select telemetry fixtures by sensor ID**

Use:

```ts
const source = state.scenario === 'data-gap'
  ? dataGapTelemetryHistoryBySensor[deviceId]
  : telemetryHistoryBySensor[deviceId]
```

Filter timestamps through `compareHistoricalDateTimes`.

- [ ] **Step 6: Select inference fixtures by sensor ID**

Use active anomaly data only for `talpha-1` in the active-anomaly scenario. Do not override fixture model metadata from arbitrary query values.

If `model_version` remains an accepted query parameter, only return matching fixture points or an empty result; do not fabricate hashes or versions.

- [ ] **Step 7: Preserve lifecycle behavior with TALPHA identifiers**

Rename generated lifecycle IDs:

```text
event_talpha_1_ack_001
event_talpha_1_resolve_001
```

Use actor `fixture-session`, preserve notes, strict event ordering, immutable append behavior, and command replay semantics.

- [ ] **Step 8: Integrate EDA facts**

Use two rows, validation counts, cadence facts, physical distributions, and scope-specific correlations. In `active-anomaly`, return one TALPHA-1 candidate outlier with score `0.028` and explicit deterministic-fixture reason.

- [ ] **Step 9: Integrate seven model tracks**

List all seven through `/api/model-evaluations`. Keep `/api/model-evaluations/:version` and the existing 404 path.

- [ ] **Step 10: Integrate two-node health scenarios**

Normal:

```ts
{ fresh_sensor_count: 2, stale_sensor_count: 0, offline_sensor_count: 0 }
```

Stale:

```ts
{ fresh_sensor_count: 1, stale_sensor_count: 1, offline_sensor_count: 0 }
```

Offline:

```ts
{ fresh_sensor_count: 1, stale_sensor_count: 0, offline_sensor_count: 1 }
```

- [ ] **Step 11: Run all handler and query tests**

```bash
npm test -- src/mocks/handlers.test.ts src/api/api.test.ts src/test/task4QueryHooks.test.tsx src/features/telemetry/queries.test.tsx src/features/inference/queries.test.tsx src/features/eda/queries.test.tsx src/features/systemHealth/query.test.tsx
```

Expected: PASS for every relative API route, TALPHA filtering, pagination, half-open ranges, historical timestamps, data gaps, deterministic scores, alert lifecycle, EDA facts, seven tracks, timeout, server errors, and retained polling data.

---

### Task 5: Adapt Overview And Sensor Detail Without Redesign

**Depends on:** Task 4

**Unblocks:** Task 10

**Worker:** `visual-engineering`

**Files:**

- Modify: `frontend/src/pages/OverviewPage.tsx`
- Modify: `frontend/src/pages/OverviewPage.test.tsx`
- Modify: `frontend/src/pages/SensorDetailPage.tsx`
- Modify: `frontend/src/pages/SensorDetailPage.test.tsx`
- Modify: `frontend/src/features/overview/SensorMatrix.tsx`
- Modify: `frontend/src/features/overview/useOverviewData.ts`
- Modify: `frontend/src/features/overview/CurrentAlertCard.tsx`
- Modify: `frontend/src/features/sensors/SensorHistoryPanel.tsx`
- Modify: `frontend/src/features/sensors/RelatedAlertHistory.tsx`
- Modify: `frontend/src/components/states/states.test.tsx`

**Hook structure:**

```ts
const talpha1 = useInferenceResultsQuery({
  deviceId: 'talpha-1',
  ...talphaValidationRange,
  bucket: 'raw',
  limit: 500,
})

const talpha2 = useInferenceResultsQuery({
  deviceId: 'talpha-2',
  ...talphaValidationRange,
  bucket: 'raw',
  limit: 500,
})

const latestScores: readonly LatestSensorScore[] = [
  latestScore('talpha-1', talpha1.data),
  latestScore('talpha-2', talpha2.data),
]
```

- [ ] **Step 1: Add failing Overview assertions**

```ts
expect(screen.getAllByRole('article', { name: /TALPHA-/ })).toHaveLength(2)
expect(screen.getByText('2/2')).toBeVisible()
expect(screen.getByText('Zona waktu tidak diketahui')).toBeVisible()
expect(screen.getByText('Data fixture historis')).toBeVisible()
expect(screen.getByText('Deteksi ambang model, bukan ground truth')).toBeVisible()
```

Assert no text matching `n1` through `n6` appears except in explicit invalid-route tests.

- [ ] **Step 2: Add failing Sensor Detail assertions**

Assert `/sensors/talpha-1` renders:

```text
TALPHA-1
2025 validation range
Zona waktu tidak diketahui
Temperature
Relative humidity
Anomaly score / threshold
Deteksi ambang model, bukan ground truth
Lihat data
```

Assert `/sensors/n1` redirects to `/`.

- [ ] **Step 3: Run page tests and confirm failure**

```bash
npm test -- src/pages/OverviewPage.test.tsx src/pages/SensorDetailPage.test.tsx src/components/states/states.test.tsx
```

Expected: FAIL with six cards, `/6`, lowercase legacy labels, current-time queries, and missing fixture disclosures.

- [ ] **Step 4: Replace six overview hooks with exactly two**

Use the exact hook structure above. Remove every `Date.now()`-derived fixture query range.

- [ ] **Step 5: Update Overview denominators and labels**

Use `/2` for telemetry and score availability. Use `sensorLabels` for cards, ARIA labels, links, and highest-breach copy.

Display breach differences with four decimals so `0.028 - 0.027078...` does not render as `+0.00`.

- [ ] **Step 6: Render exactly two full-width desktop cards**

Keep the existing grid and visual language. Change only the large breakpoint from one-third width to half width:

```tsx
<Grid key={sensorId} size={{ xs: 12, md: 6, lg: 6 }}>
```

- [ ] **Step 7: Add permanent provenance text**

Place the following near page headings and score contexts:

```text
Data fixture historis
Zona waktu tidak diketahui
Deteksi ambang model, bukan ground truth
```

Do not introduce a new banner component or layout region.

- [ ] **Step 8: Update detail snapshot and history labels**

Display uppercase labels while preserving lowercase route IDs. Keep current temperature, RH, freshness, score, related alerts, and bounded table placement.

- [ ] **Step 9: Update empty-state wording**

Use:

```text
Tidak ada sampel fixture historis pada rentang 2025 yang dipilih.
```

Do not imply live telemetry absence.

- [ ] **Step 10: Preserve chart accessibility and actual gaps**

Keep `connectNulls: false`, skip animations, semantic chart groups, ARIA descriptions, anomaly markers, and `Lihat data`.

- [ ] **Step 11: Run Task 5 tests**

```bash
npm test -- src/pages/OverviewPage.test.tsx src/pages/SensorDetailPage.test.tsx src/components/charts/options.test.ts src/components/states/states.test.tsx
```

Expected: PASS with exactly two cards, `/2`, canonical order, uppercase labels, real timestamp spacing, visible gaps, per-node Arm B scores, historical copy, and no joint model scores.

---

### Task 6: Adapt Alerts And Fixture Lifecycle Copy

**Depends on:** Task 4

**Unblocks:** Task 10

**Worker:** `visual-engineering`

**Files:**

- Modify: `frontend/src/pages/AlertsPage.tsx`
- Modify: `frontend/src/pages/AlertsPage.test.tsx`
- Modify: `frontend/src/features/alerts-ui/AlertsGrid.tsx`
- Modify: `frontend/src/features/alerts-ui/AlertEventHistory.tsx`
- Modify: `frontend/src/features/alerts-ui/AlertLifecycleActions.tsx`
- Modify: `frontend/src/features/overview/CurrentAlertCard.tsx`
- Modify: `frontend/src/features/sensors/RelatedAlertHistory.tsx`

- [ ] **Step 1: Add failing Alerts page tests**

Assert the sensor filter contains:

```text
All sensors
TALPHA-1
TALPHA-2
```

Assert the grid, history entry, current-alert card, and related history each expose:

```text
Deteksi ambang model, bukan ground truth
```

Assert the page exposes:

```text
Data fixture historis
Zona waktu tidak diketahui
Lifecycle ini hanya state interaksi fixture dalam sesi.
```

- [ ] **Step 2: Run Alerts tests and confirm failure**

```bash
npm test -- src/pages/AlertsPage.test.tsx src/features/alerts/lifecycle.test.tsx
```

Expected: FAIL with legacy labels and operational-history wording.

- [ ] **Step 3: Update filter labels**

Render options through `sensorLabels`. Keep query values and API fields lowercase.

- [ ] **Step 4: Add a detection-basis grid column**

Add:

```ts
{
  field: 'detection_basis',
  headerName: 'Detection basis',
  minWidth: 240,
  flex: 1.5,
  sortable: false,
  valueFormatter: () => 'Deteksi ambang model, bukan ground truth',
}
```

This ensures every grid row carries the required disclosure.

- [ ] **Step 5: Replace operational provenance wording**

Remove claims such as immutable operational history, inference workers, real operators, deployment, notifications, or real acknowledgement history.

Use `fixture-session` for newly created lifecycle actors.

- [ ] **Step 6: Preserve lifecycle controls**

Keep detected → acknowledged → resolved, conflict responses, retries, idempotent replay, notes, and in-session state.

Add accessible helper text that the controls affect only fixture-session state.

- [ ] **Step 7: Update event and related-history entries**

Every rendered event must display its detection basis and uppercase node label. Keep timestamps and notes visible.

- [ ] **Step 8: Run Task 6 tests**

```bash
npm test -- src/pages/AlertsPage.test.tsx src/features/alerts/lifecycle.test.tsx src/mocks/handlers.test.ts
```

Expected: PASS with two-node filters, deterministic fixture disclosures in every required alert surface, and unchanged lifecycle behavior.

---

### Task 7: Adapt EDA To TALPHA Validation Samples

**Depends on:** Task 4

**Unblocks:** Task 10

**Worker:** `visual-engineering`

**Files:**

- Modify: `frontend/src/pages/EdaPage.tsx`
- Modify: `frontend/src/pages/EdaPage.test.tsx`
- Modify: `frontend/src/features/eda/EdaFilters.tsx`
- Modify: `frontend/src/features/eda/CoveragePanel.tsx`
- Modify: `frontend/src/features/eda/MissingnessPanel.tsx`
- Modify: `frontend/src/features/eda/DistributionPanel.tsx`
- Modify: `frontend/src/features/eda/TemporalPatternsPanel.tsx`
- Modify: `frontend/src/features/eda/CorrelationPanel.tsx`
- Modify: `frontend/src/features/eda/SensorComparisonPanel.tsx`
- Modify: `frontend/src/features/eda/CandidateOutliersPanel.tsx`

- [ ] **Step 1: Add failing EDA tests**

Assert:

```ts
expect(screen.getAllByRole('row')).toContainRowsFor(['TALPHA-1', 'TALPHA-2'])
expect(screen.getByText(/86,104/)).toBeVisible()
expect(screen.getByText(/median cadence.*6 seconds/i)).toBeVisible()
expect(screen.getByText(/2 gaps/i)).toBeVisible()
expect(screen.getByText('Zona waktu tidak diketahui')).toBeVisible()
expect(screen.getByText('Deteksi ambang model, bukan ground truth')).toBeVisible()
```

Assert candidate outliers are described as exploratory fixture candidates, not confirmed anomalies.

- [ ] **Step 2: Run EDA tests and confirm failure**

```bash
npm test -- src/pages/EdaPage.test.tsx src/features/eda/queries.test.tsx
```

Expected: FAIL with six rows, hardcoded six-sample statistics, 2026 timestamps, and unsupported score claims.

- [ ] **Step 3: Update EDA controls**

Render only TALPHA-1 and TALPHA-2. Preserve current fields, bins, sample-size controls, temporal controls, and query parameters.

- [ ] **Step 4: Display canonical coverage and cadence**

Show validation row counts, 100% observed fixture-row coverage, two gaps, the 600-second threshold, and actual non-gap cadence statistics.

Do not infer regular cadence from array index.

- [ ] **Step 5: Display physical distributions**

Use inverse-scaled Celsius and RH values. Do not display normalized `0..1` values as physical telemetry.

- [ ] **Step 6: Preserve temporal gaps**

Use source timestamps and null breaks. Show both segment-boundary gaps.

- [ ] **Step 7: Display two comparison rows**

Use uppercase labels and the per-node statistics in Task 3.

- [ ] **Step 8: Qualify score and candidate panels**

Add:

```text
Deteksi ambang model, bukan ground truth
Kandidat eksploratif dari fixture deterministik, bukan label anomali.
```

- [ ] **Step 9: Preserve panel failure isolation**

A failed distribution, temporal, or correlation request must not replace confirmed data in another panel.

- [ ] **Step 10: Run Task 7 tests**

```bash
npm test -- src/pages/EdaPage.test.tsx src/features/eda/queries.test.tsx src/components/charts/options.test.ts
```

Expected: PASS with two comparison rows, physical distributions, actual cadence, both gaps, validation-derived correlations, deterministic score wording, independent retries, and bounded chart/table alternatives.

---

### Task 8: Present Exactly Seven Validation-Only Model Tracks

**Depends on:** Task 4

**Unblocks:** Task 10

**Worker:** `visual-engineering`

**Files:**

- Modify: `frontend/src/pages/ModelEvaluationPage.tsx`
- Modify: `frontend/src/pages/ModelEvaluationPage.test.tsx`
- Modify: `frontend/src/features/modelEvaluation/VersionSelect.tsx`
- Modify: `frontend/src/features/modelEvaluation/MetricsPanel.tsx`
- Verify: `frontend/src/features/modelEvaluation/LabeledMetricsPanels.tsx`
- Modify: `frontend/src/features/modelEvaluation/queries.ts` only if normalization assumes old version names

**MetricsPanel interface:**

```ts
export interface MetricsPanelProps {
  artifact: ModelEvaluationDetail
}

export function MetricsPanel({ artifact }: MetricsPanelProps): React.JSX.Element
```

It must render only:

```text
Threshold
Validation windows
Strict exceedance count
Strict exceedance fraction
Threshold source split
Threshold percentile
Threshold comparison
```

- [ ] **Step 1: Add failing seven-track tests**

Assert the selector has exactly seven options with the labels listed in Task 3.

Assert each selected track displays:

```text
score_key
score semantics
Validation only
86,017
Validation p99.5
Strict comparison >
No labeled ground truth
Test split not evaluated
```

- [ ] **Step 2: Add forbidden-claim assertions**

```ts
for (const forbidden of [
  /accuracy/i,
  /\bF1\b/i,
  /\bROC\b/i,
  /\bAUC\b/i,
  /precision/i,
  /recall/i,
  /confusion matrix/i,
  /average precision/i,
  /best model/i,
  /ranking/i,
  /production candidate/i,
  /deployment status/i,
]) {
  expect(screen.queryByText(forbidden)).not.toBeInTheDocument()
}
```

- [ ] **Step 3: Run Model Evaluation tests and confirm failure**

```bash
npm test -- src/pages/ModelEvaluationPage.test.tsx
```

Expected: FAIL because only two labeled production-candidate fixtures exist and labeled panels are rendered.

- [ ] **Step 4: Rename selector copy without renaming route state**

Change `Model version` to `Evaluation track`. Keep `model_version` in the URL to avoid changing the existing interaction seam.

Render `summary.label` in options and retain `summary.version` as the option value.

- [ ] **Step 5: Replace metadata content**

Display label, model, track, score key, score semantics, evaluation period, validation-only scope, test-not-evaluated status, window count, threshold, and policy.

Remove fabricated created-at and artifact-hash display when values are null.

- [ ] **Step 6: Replace MetricsPanel data**

Render only calibration facts through the new `artifact` prop. Do not generically surface unknown metrics.

- [ ] **Step 7: Preserve hidden labeled panels**

Continue rendering:

```tsx
<LabeledMetricsPanels artifact={detail.data} />
```

The component must return `null` because all seven records have `has_labeled_ground_truth: false`.

- [ ] **Step 8: Display the canonical disclaimer**

Render the exact `comparison_summary.json` disclaimer beneath the calibration facts.

- [ ] **Step 9: Run Task 8 tests**

```bash
npm test -- src/pages/ModelEvaluationPage.test.tsx src/contracts/contracts.test.ts
```

Expected: PASS with exactly seven tracks, no labeled charts or unsupported performance claims, and all calibration metadata visible.

---

### Task 9: Mark System Health As Historical Fixture Data

**Depends on:** Task 4

**Unblocks:** Task 10

**Worker:** `visual-engineering`

**Files:**

- Modify: `frontend/src/pages/SystemHealthPage.tsx`
- Modify: `frontend/src/pages/SystemHealthPage.test.tsx`
- Modify: `frontend/src/features/systemHealth/StatusSnapshot.tsx`
- Modify: `frontend/src/features/systemHealth/ServiceStatusTable.tsx`
- Modify: `frontend/src/features/systemHealth/query.test.tsx`

- [ ] **Step 1: Add failing health semantics tests**

Assert:

```text
Data fixture historis
Bukan status deployment langsung
Zona waktu tidak diketahui
Fresh sensors: 2
```

Assert every service row reports `unknown` liveness and readiness.

Assert database, model loading, inference worker, liveness, and readiness are not presented as direct evidence.

- [ ] **Step 2: Run health tests and confirm failure**

```bash
npm test -- src/pages/SystemHealthPage.test.tsx src/features/systemHealth/query.test.tsx
```

Expected: FAIL with six sensors, ready/alive rows, and direct deployment wording.

- [ ] **Step 3: Replace the page introduction**

Use:

```text
Data fixture historis. Bukan status deployment langsung.
```

Explain that the page does not establish current liveness, readiness, database state, model loading, or worker state.

- [ ] **Step 4: Separate poll freshness from corpus time**

Keep the existing displayed-at and poll-age behavior. Label `snapshot.telemetry.latest_ts` as historical corpus time and place `Zona waktu tidak diketahui` next to it.

- [ ] **Step 5: Render fixture-only service rows**

Keep the table layout and columns. Display `unknown` states textually so meaning does not rely on color.

- [ ] **Step 6: Preserve polling-error behavior**

Keep retained data, retry action, warning notice, and `Current reachability: Unknown`.

- [ ] **Step 7: Run Task 9 tests**

```bash
npm test -- src/pages/SystemHealthPage.test.tsx src/features/systemHealth/query.test.tsx
```

Expected: PASS with two-node totals, fixture-only health semantics, unknown service states, corpus timezone copy, retained-data polling behavior, and no live-deployment claim.

---

### Task 10: Update E2E Workflows, Accessibility, Responsive Coverage, And Visual Baselines

**Depends on:** Tasks 5–9

**Unblocks:** Task 11

**Worker:** `visual-engineering`

**Required skills:** `playwright`, `visual-qa`

**Files:**

- Modify: `frontend/tests/e2e/helpers.ts`
- Modify: `frontend/tests/e2e/overview.spec.ts`
- Modify: `frontend/tests/e2e/sensor-detail.spec.ts`
- Modify: `frontend/tests/e2e/alerts.spec.ts`
- Modify: `frontend/tests/e2e/analysis.spec.ts`
- Modify: `frontend/tests/e2e/system-health.spec.ts`
- Modify: `frontend/tests/e2e/layout.spec.ts`
- Modify: `frontend/tests/e2e/keyboard.spec.ts`
- Modify: `frontend/tests/e2e/visual.spec.ts`
- Modify: `frontend/playwright.config.ts`
- Replace: `frontend/tests/e2e/visual.spec.ts-snapshots/`
- Modify: `frontend/tests/production/verify-dist.test.mjs`

**Playwright configuration:**

```ts
snapshotPathTemplate:
  '{testDir}/{testFilePath}-snapshots/{projectName}/{arg}{ext}'
```

```ts
testMatch:
  width === 1440 ? undefined : /(?:layout|visual)\.spec\.ts/
```

**Visual routes:**

```ts
const routes = [
  { route: '/', snapshot: 'overview.png' },
  { route: '/sensors/talpha-1', snapshot: 'sensors-talpha-1.png' },
  { route: '/alerts', snapshot: 'alerts.png' },
  { route: '/eda', snapshot: 'eda.png' },
  { route: '/model-evaluation', snapshot: 'model-evaluation.png' },
  { route: '/system-health', snapshot: 'system-health.png' },
] as const
```

**Expected baseline tree:**

```text
frontend/tests/e2e/visual.spec.ts-snapshots/
  desktop-1280/
    overview.png
    sensors-talpha-1.png
    alerts.png
    eda.png
    model-evaluation.png
    system-health.png
  desktop-1440/
    overview.png
    sensors-talpha-1.png
    alerts.png
    eda.png
    model-evaluation.png
    system-health.png
  desktop-1920/
    overview.png
    sensors-talpha-1.png
    alerts.png
    eda.png
    model-evaluation.png
    system-health.png
```

- [ ] **Step 1: Update E2E expectations before rebaselining**

Assert exactly two Overview articles, `/2` summaries, TALPHA routes, unknown-timezone text, alert fixture disclosures, two EDA rows, seven tracks, hidden labeled panels, and historical health wording.

- [ ] **Step 2: Add all-six legacy-route rejection coverage**

```ts
for (const legacyId of ['n1', 'n2', 'n3', 'n4', 'n5', 'n6']) {
  test(`redirects retired sensor ${legacyId}`, async ({ page }) => {
    await page.goto(`/sensors/${legacyId}`)
    await expect(page).toHaveURL('/')
  })
}
```

- [ ] **Step 3: Preserve role-based and keyboard locators**

Continue using roles, labels, headings, and visible names. Do not add `data-testid` unless no semantic locator exists.

- [ ] **Step 4: Preserve keyboard workflow coverage**

Verify permanent navigation, filter controls, alert lifecycle controls, grid selection, retry buttons, `Lihat data`, and dialog closure remain keyboard reachable with visible focus.

- [ ] **Step 5: Preserve no-overflow checks**

Keep existing narrow-width and desktop assertions. Do not introduce a new mobile navigation mode.

- [ ] **Step 6: Add stable ARIA assertions**

Assert page landmarks, headings, chart role/name/description, status text, and bounded data alternatives. Use Playwright ARIA snapshots only for stable navigation and landmark structures.

- [ ] **Step 7: Run E2E tests before updating screenshots**

```bash
npm run test:e2e
```

Expected: functional tests PASS after updating expectations; visual tests FAIL because the six legacy 1440 baselines no longer match and 1280/1920 baselines do not yet exist.

- [ ] **Step 8: Update project-aware visual coverage**

Apply the exact Playwright configuration above. Keep font readiness, full-page screenshots, hidden caret, fixed fixtures, and disabled animations.

- [ ] **Step 9: Generate all eighteen baselines**

```bash
npm run test:e2e -- tests/e2e/visual.spec.ts --update-snapshots
```

Expected: PASS and write six screenshots for each of `desktop-1280`, `desktop-1440`, and `desktop-1920`.

- [ ] **Step 10: Run visual tests without update mode**

```bash
npm run test:e2e -- tests/e2e/visual.spec.ts
```

Expected: PASS against all eighteen committed TALPHA baselines.

- [ ] **Step 11: Inspect visual output with visual-qa**

Verify shell, route ordering, component hierarchy, theme, typography, spacing, focus indicators, chart boundaries, card composition, and page density remain consistent with the existing application. Only data-driven two-node differences may change.

- [ ] **Step 12: Update production artifact guards**

Replace legacy fixture markers with TALPHA markers:

```js
['mock alert fixture', /alert_talpha_1_active/],
['mock timestamp fixture', /2025-12-18T07:52:42/],
['sibling NPZ path', /val\.npz|test\.npz/],
['sibling repository path', /skripsih\/anomaly-detection\/data\/processed/],
```

Continue requiring all relative API paths and rejecting absolute API origins, MSW, fixture modules, scenarios, and mock request IDs.

- [ ] **Step 13: Run Task 10 browser and production checks**

```bash
npm run build
npm run test:production
npm run test:e2e
```

Expected: production build succeeds, production artifacts contain no fixture implementation or sibling path, and all functional/layout/keyboard/visual browser tests pass.

---

### Task 11: Final Cleanup And Full Verification

**Depends on:** Task 10

**Unblocks:** Completion

**Files:**

- Modify only files implicated by verification failures.
- Do not modify the approved design spec.
- Do not modify the unrelated backend plan.
- Do not modify the sibling repository.

- [ ] **Step 1: Scan for stale six-node counts and dates**

Run from the platform root:

```bash
rg -n '/6\b|2026-07-(18|19)|Selected production candidate|Current deterministic baseline evaluation' frontend/src frontend/tests
```

Expected: no matches.

- [ ] **Step 2: Audit remaining legacy IDs**

```bash
rg -n '\bn[1-6]\b|sensors-n[1-6]' frontend/src frontend/tests
```

Expected: matches only in explicit legacy-rejection tests or forbidden-content checks. No runtime fixture, route, selector, label, or screenshot name may match.

- [ ] **Step 3: Audit unsupported provenance**

```bash
rg -n 'inference-worker|actor: .operator.|deployment status|production candidate|best model' frontend/src frontend/tests
```

Expected: `inference-worker` may appear only as an `unknown` fixture service row with explicit no-evidence wording. No real operator, deployment, ranking, or production-candidate claim remains.

- [ ] **Step 4: Audit TALPHA timezone claims**

```bash
rg -n '\bUTC\b|2025-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z' frontend/src frontend/tests
```

Expected: no TALPHA fixture timestamp contains `Z` and no TALPHA view claims UTC. Any remaining offset timestamp must be unrelated to historical TALPHA fixture data and reviewed individually.

- [ ] **Step 5: Audit runtime sibling access**

```bash
rg -n '/home/reky/college/skripsih/anomaly-detection|val\.npz|test\.npz|data/processed/talpha' frontend/src
```

Expected: no matches.

- [ ] **Step 6: Audit model-evaluation claims**

```bash
rg -ni 'accuracy|\bf1\b|\broc\b|\bauc\b|precision|recall|confusion matrix|average precision|ranking|best model' frontend/src/mocks/fixtures/modelEvaluations.ts frontend/src/pages/ModelEvaluationPage.tsx
```

Expected: no matches.

`LabeledMetricsPanels.tsx` may retain generic labeled-chart implementation, but it must not render for any TALPHA fixture.

- [ ] **Step 7: Run lint**

```bash
npm run lint
```

Expected: PASS with zero ESLint errors.

- [ ] **Step 8: Run the complete unit and contract suite**

```bash
npm test
```

Expected: PASS with no skipped TALPHA adaptation tests and no stale six-device expectation.

- [ ] **Step 9: Run typecheck and production build**

```bash
npm run build
```

Expected: PASS for `tsc -b` and Vite production build.

- [ ] **Step 10: Verify production isolation**

```bash
npm run test:production
```

Expected: PASS; production output contains no MSW, fixtures, scenario state, sibling paths, absolute API origin, or canonical NPZ filename.

- [ ] **Step 11: Run all browser tests**

```bash
npm run test:e2e
```

Expected: PASS for functional workflows, keyboard navigation, narrow-width overflow checks, three desktop visual projects, unknown-timezone copy, seven validation tracks, and historical health semantics.

- [ ] **Step 12: Perform final spec-coverage review**

Confirm each acceptance criterion maps to passing evidence:

| Acceptance Criterion | Evidence |
|---|---|
| Existing shell, theme, six routes, hierarchy, controls | Layout, keyboard, and visual E2E |
| Only two TALPHA boundaries | Contract, route, handler, selector tests |
| Exactly two Overview cards and `/2` | Overview unit and E2E |
| Canonical inverse-scaled validation telemetry | Fixture extraction assertions and handler tests |
| Metadata-driven dates, cadence, gaps | Contract, handler, chart, EDA tests |
| No UTC claim | Timestamp schema, cleanup scan, page/E2E copy |
| Exact Arm B thresholds and strict `>` | Fixture and handler tests |
| Alerts remain operable but fixture-only | Lifecycle unit, handler, page, and E2E tests |
| Exactly seven validation-only tracks | Contract, page, and E2E tests |
| No labeled or ranking claims | Contract guard, forbidden-copy tests, cleanup scan |
| Two-node historical System Health | Health unit and E2E tests |
| Accessibility and responsive behavior preserved | Keyboard, ARIA, layout, and visual checks |
| No new dependency or runtime sibling access | Lockfile unchanged and production isolation test |

Expected: every row has passing automated evidence and no unresolved manual exception.

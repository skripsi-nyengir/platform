# TALPHA Dataset UI Adaptation Design

**Date:** 2026-07-21  
**Status:** Approved, implementation-ready  
**Scope:** Direct replacement of legacy six-device frontend data with the canonical two-node TALPHA corpus.

> **Approved no-redesign boundary:** This is a dataset replacement only. Preserve the application shell, six routes, page structure, components, interaction model, dark theme, and existing desktop responsive behavior. Do not redesign the dashboard.

## Authority and fixed decisions

This document supersedes legacy six-device assumptions for the TALPHA frontend adaptation only. The frontend remains fixture-first and keeps its typed API, MSW, page, and test seams.

- Replace legacy data directly. Do not retain `n1` through `n6` aliases, compatibility maps, generic dataset adapters, or a selectable dataset mode.
- The only logical IDs are `talpha-1` and `talpha-2`. Their visible labels are `TALPHA-1` and `TALPHA-2`.
- Each node has temperature and relative humidity only. Use `temperature_c` and `relative_humidity_pct` in the existing frontend contract shape.
- No dependency is added. No sibling repository file is changed. The browser, Vite, MSW, and production bundle must never read the sibling repository at runtime.
- Keep Indonesian product-copy conventions. Use explicit copy such as `Data fixture historis`, `Zona waktu tidak diketahui`, and `Deteksi ambang model, bukan ground truth` where those facts are shown.

## Canonical sources and provenance

The implementation may read these sibling-repository sources only while preparing checked-in frontend fixtures. It must not read them from frontend runtime code.

- `/home/reky/college/skripsih/anomaly-detection/data/processed/talpha/metadata.json` is the corpus authority. It declares `talpha_2node_v1`, four channels, split metadata, scaler metadata, `max_gap_seconds`, and the corpus `timestamp_range`.
- `/home/reky/college/skripsih/anomaly-detection/data/processed/talpha/val.npz` is the sole sample source. Read `values`, `timestamps`, and `seg_bounds`; use only its validation split for displayed telemetry fixtures.
- `/home/reky/college/skripsih/anomaly-detection/runs/benchmark_validation_figures/comparison/comparison_summary.json` is the authoritative current run record. It is `benchmark_validation_calibration_v1`, `validation_only: true`, and `test_evaluated: false`.
- `/home/reky/college/skripsih/anomaly-detection/configs/conv1d_talpha.yaml` is the source for the active Conv1D Arm B channel mapping.

`metadata.json` records 574,027 rows from `2025-07-22 18:08:05` through `2025-12-24 13:18:53`. It also records the validation span from `2025-12-11 23:50:35` through `2025-12-18 07:52:42`. Date controls, labels, fixture ranges, and empty-state wording must derive from this metadata, not from the old 2026 fixture dates.

The source timestamps are Unix seconds, but the corpus timezone is unknown. Convert them to preserved calendar values without an offset, do not append `Z`, and do not label any TALPHA time as UTC. Historical contracts used by these fixtures must accept the exact timezone-unqualified TALPHA timestamp form for `ts`, `window_start_ts`, `window_end_ts`, alert fixture times, and fixture health times. Every affected view displays `Zona waktu tidak diketahui` beside its time context.

Map source columns as follows:

- `talpha-1` / `TALPHA-1`: `suhu1`, `rh1`, indices `[0, 1]`.
- `talpha-2` / `TALPHA-2`: `suhu2`, `rh2`, indices `[2, 3]`.

The source configuration describes these physical semantics as inferred and pending confirmation. The UI must not infer a room, location, installation role, or device topology beyond the two displayed TALPHA labels.

Never source fixtures, model metadata, or UI copy from:

- `/home/reky/college/skripsih/anomaly-detection/data/processed/6device/`
- `/home/reky/college/skripsih/anomaly-detection/data/processed/PR00188-1/`
- `/home/reky/college/skripsih/anomaly-detection/notebooks/outputs/conv1d_benchmark_summary.json`
- `/home/reky/college/skripsih/anomaly-detection/notebooks/outputs/ewma_benchmark_summary.json`
- `/home/reky/college/skripsih/anomaly-detection/notebooks/outputs/pca_benchmark_summary.json`
- `/home/reky/college/skripsih/anomaly-detection/runs/validation_tuning_seed42_v1/`
- `/home/reky/college/skripsih/anomaly-detection/runs/conv1d_abc_pilot/`, `/home/reky/college/skripsih/anomaly-detection/runs/conv1d_abc_pilot_cap100/`, `/home/reky/college/skripsih/anomaly-detection/runs/conv1d_abc_pilot_cap200/`, and `/home/reky/college/skripsih/anomaly-detection/runs/conv1d_abc_sanity/`

The locked test split at `/home/reky/college/skripsih/anomaly-detection/data/processed/talpha/test.npz` is not a fixture source and is never displayed as evaluation evidence.

## Architecture and fixture data flow

The implementation changes only the existing frontend data path:

```text
canonical metadata + val.npz + comparison_summary.json
  -> offline fixture preparation
  -> checked-in TALPHA fixtures
  -> existing MSW handlers and typed adapters
  -> existing pages and components
```

No runtime cross-repository read, symlink, Vite alias, filesystem fetch, build-time import from the sibling repository, or new service is permitted. `frontend/src/mocks/fixtures/` contains static deterministic data after preparation. `frontend/src/mocks/handlers.ts` continues to expose the current relative API routes. Later backend work may serve the same direct TALPHA contract, but it is outside this adaptation.

Update these direct seams, not a new abstraction:

- `frontend/src/contracts/common.ts`, `frontend/src/contracts/telemetry.ts`, `frontend/src/contracts/inference.ts`, `frontend/src/contracts/alerts.ts`, `frontend/src/contracts/eda.ts`, `frontend/src/contracts/modelEvaluation.ts`, and `frontend/src/contracts/systemHealth.ts`
- `frontend/src/mocks/fixtures/telemetry.ts`, `frontend/src/mocks/fixtures/inference.ts`, `frontend/src/mocks/fixtures/alerts.ts`, `frontend/src/mocks/fixtures/eda.ts`, `frontend/src/mocks/fixtures/modelEvaluations.ts`, and `frontend/src/mocks/fixtures/systemHealth.ts`
- `frontend/src/mocks/handlers.ts` and `frontend/src/mocks/scenario.ts`
- `frontend/src/pages/OverviewPage.tsx`, `frontend/src/pages/SensorDetailPage.tsx`, `frontend/src/pages/AlertsPage.tsx`, `frontend/src/pages/EdaPage.tsx`, `frontend/src/pages/ModelEvaluationPage.tsx`, and `frontend/src/pages/SystemHealthPage.tsx`
- `frontend/src/features/overview/SensorMatrix.tsx`, `frontend/src/features/overview/useOverviewData.ts`, `frontend/src/features/sensors/SensorHistoryPanel.tsx`, `frontend/src/features/sensors/RelatedAlertHistory.tsx`, `frontend/src/features/alerts-ui/AlertsGrid.tsx`, `frontend/src/features/alerts-ui/AlertEventHistory.tsx`, `frontend/src/features/modelEvaluation/MetricsPanel.tsx`, `frontend/src/features/modelEvaluation/LabeledMetricsPanels.tsx`, `frontend/src/features/systemHealth/StatusSnapshot.tsx`, and `frontend/src/features/systemHealth/ServiceStatusTable.tsx`.

`sensorIds` becomes the closed two-item set `['talpha-1', 'talpha-2']`. Response maximums, fixture arrays, selectors, filters, query validation, and navigation targets must follow that same set. Unknown IDs, including `n1` through `n6`, remain invalid and redirect or return the existing validation error path.

Use source timestamps as the x-axis values. Determine cadence, coverage, and gaps from timestamp deltas and `seg_bounds`, never from array index or an equal-spacing assumption. A missing interval remains a chart gap and a reported gap even when neighboring samples share the same visual bucket.

## Scores and alerts

Real Conv1D Arm B score arrays are unavailable. Per-node overview scores, sensor-detail score lanes, EDA score samples, and alert scores are fixed demo fixtures keyed to the authoritative Arm B validation thresholds:

- `talpha-1`: `global_mae > 0.02707822278141974`
- `talpha-2`: `global_mae > 0.031537856459617604`

Each fixture score is deterministic. Its `threshold` is the exact node threshold above, and `is_anomaly` is exactly `score > threshold`, matching the authoritative strict-exceedance policy. The score values are demonstration values, not recovered Conv1D outputs, labels, or incident observations.

Alerts remain in their current layout and lifecycle controls. Every alert card, grid row, history entry, and detail view must state that it is a deterministic threshold-model detection fixture, not ground-truth anomaly data. Alert lifecycle entries are fixture interaction state only. Do not claim an inference worker, operator, deployment, notification delivery, acknowledgement history, resolution history, or other real alert provenance. Existing acknowledge and resolve behavior remains testable inside the fixture session.

## Page behavior

### Overview

Keep the heading, four summary cards, attention queue, and `SensorMatrix`. Render exactly two node cards in canonical order, `TALPHA-1` then `TALPHA-2`. Change every availability and score denominator from `/6` to `/2`; the telemetry-complete check also requires exactly those two IDs. Do not leave six-card skeletons, empty retired-device slots, or legacy labels. Current temperature, RH, freshness, deterministic threshold score, and alert links retain their current placement and accessible labels.

### Sensor Detail and History

Keep `/sensors/:sensorId`, the temporal filters, snapshot, aligned temperature/RH/score lanes, related alerts, and `Lihat data` table. The selector and route validation admit only the two TALPHA IDs. Source values set the temperature and RH ranges, and the deterministic Arm B score is the only score lane. Preserve true timestamp spacing and gaps. The detail page does not show canonical four-channel or joint-model scores.

### Alerts

Keep the filterable grid, event history, and acknowledged-before-resolved rule. Filters list only TALPHA-1 and TALPHA-2. The detection label identifies a threshold-model fixture rather than a verified anomaly. Current lifecycle state remains an in-session demo state and must not be presented as a historical operational record.

### EDA

Keep the current EDA panels and controls. Quality, coverage, missingness, distributions, temporal patterns, correlations, comparisons, and candidate outliers use TALPHA validation samples and the two source channel pairs. Sensor comparison has two rows. Candidate outliers and score visualizations are exploratory deterministic threshold fixtures, never labels or confirmed anomalies. Corpus range, actual cadence, and gaps are metadata and timestamp driven.

### Model Evaluation

This is the only page that may show joint canonical-four-channel tracks. Show exactly these seven validation-only tracks from `comparison_summary.json`:

1. EWMA, `canonical_4ch`
2. PCA, `canonical_4ch`
3. Conv1D, `arm_a`
4. Conv1D, `arm_b_talpha1`
5. Conv1D, `arm_b_talpha2`
6. TranAD, `canonical_4ch`
7. USAD, `canonical_4ch`

Show each track's label, `score_key`, score semantics, validation-only scope, `n_val_windows: 86,017`, and validation-p99.5 threshold policy. Mark every entry `No labeled ground truth` and `Test split not evaluated`. Do not render or claim accuracy, F1, ROC, AUC, precision, recall, confusion matrix, average precision, a best model, ranking, production candidate, deployment status, or performance conclusion. Conditional labeled-metric panels remain hidden for all seven tracks.

### System Health

Keep the snapshot and service-table layout, but report two nodes in telemetry totals. Mark the whole view as `Data fixture historis` and `Bukan status deployment langsung`. The snapshot is not live liveness, readiness, database, model-loading, or inference-worker evidence. Use unknown or fixture-only wording for those service rows, retain polling-error treatment, and show the corpus time with the unknown-timezone label.

## States, accessibility, and responsive behavior

Keep the existing layout-matched skeletons, empty states, retained stale data, polling-failure notices, bounded API-error panels, request IDs, retries, and partial-panel isolation. Empty TALPHA ranges explain that no historical fixture sample exists in the selected 2025 range. A failure must not replace confirmed data in another panel. No state may fabricate live telemetry, a current deployment state, a real score, or a real alert history.

Preserve visible keyboard focus, semantic headings, accessible status text, chart ARIA summaries, and the bounded `Lihat data` alternative. Status and alert meaning never rely on color alone. Keep the existing desktop breakpoints and no-horizontal-overflow behavior. Update counts and card contents only; do not add a mobile navigation design or change the shell.

## Testing and visual regression

Update the existing tests rather than adding a new test framework or a parallel fixture system.

- Unit and contract tests cover the two allowed IDs, rejection of all six legacy IDs, TALPHA labels, metadata-derived 2025 range, source channel mapping, exact Arm B thresholds, strict score comparison, timestamp-based gaps, fixture provenance text, and no-offset historical timestamp display.
- `frontend/src/mocks/handlers.test.ts`, feature query tests, and state tests cover two-node responses, empty selections, data gaps, polling errors, threshold-demo alerts, and retained lifecycle test behavior.
- `frontend/tests/e2e/overview.spec.ts`, `frontend/tests/e2e/sensor-detail.spec.ts`, `frontend/tests/e2e/alerts.spec.ts`, `frontend/tests/e2e/analysis.spec.ts`, `frontend/tests/e2e/system-health.spec.ts`, `frontend/tests/e2e/layout.spec.ts`, `frontend/tests/e2e/keyboard.spec.ts`, and `frontend/tests/e2e/visual.spec.ts` cover only two TALPHA cards or rows where applicable, `/2` summaries, routes, keyboard navigation, unknown-timezone text, validation-only model evaluation, and fixture/historical health wording.
- Rebaseline screenshots only for the data-driven two-node differences. Capture the existing desktop visual set at 1280, 1440 by 900, and 1920 widths with deterministic fixtures and animations disabled. Confirm the shell, route order, component hierarchy, theme, focus indicators, and page composition did not change.
- Run the existing lint, typecheck, unit suite, end-to-end suite, production build, and visual-regression checks. The test suite must contain no six-device expectation or stale 2026 fixture date.

## Non-goals

- A dashboard redesign, route change, component rewrite, theme change, generic dataset layer, compatibility aliases, dependency addition, backend implementation, runtime data import, or sibling-repository change.
- Live telemetry, real-time inference, ground-truth anomalies, real alert lifecycle provenance, deployment claims, or use of the locked test split.
- Final classification metrics, ROC, precision-recall, F1, model ranking, or a production-readiness claim.

## Acceptance criteria

1. The rendered application still has the same shell, theme, six routes, page layouts, controls, and desktop responsive behavior, with no redesigned dashboard surface.
2. Every frontend sensor boundary accepts only `talpha-1` and `talpha-2`, displays TALPHA-1 and TALPHA-2, and has no legacy ID alias or six-device fixture.
3. Overview renders exactly two node cards and all telemetry and score summary denominators are `/2`.
4. Telemetry and EDA samples originate from the canonical TALPHA validation NPZ; dates, gaps, and coverage are metadata and timestamp driven; the UI never claims UTC.
5. Per-node score and alert fixtures use the exact Conv1D Arm B thresholds, strict `score > threshold`, and clear deterministic-demo wording without a ground-truth claim.
6. Alerts remain operable as fixture interactions but never claim genuine alert or lifecycle provenance.
7. Model Evaluation presents exactly seven validation-only tracks, confines joint tracks to that page, and hides all labeled metrics and ranking claims.
8. System Health totals two nodes and clearly says that its data is historical fixture data, not live deployment evidence.
9. All listed tests, production build, and updated desktop visual regressions pass without new dependencies or runtime reads outside the platform repository.

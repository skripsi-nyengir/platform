# MUI X Charts Full Migration Implementation Plan

> **For implementation:** Execute this plan task-by-task. Keep the existing API contracts, table alternatives, accessibility behavior, and loading/empty/error states unchanged.

**Goal:** Replace every ECharts visualization in the frontend with MUI X Charts Community 9.10.0 and an accessible MUI Table confusion matrix, including separate Temperature and RH sparklines on every Overview sensor card.

**Architecture:** Remove the generic `EChart` option-based rendering layer. Keep the useful domain calculations in the existing option-builder modules, but turn them into typed, renderer-agnostic data mappers consumed directly by MUI X components. Reuse the existing chart framing, summaries, filters, tables, and state handling rather than introducing a second compatibility layer.

**Tech stack:** React 19, TypeScript 6.0.2, Material UI 9.2.0, MUI X Charts Community 9.10.0, Vitest, Testing Library, Playwright.

**Constraints:**

- This workspace is not a Git repository. Do not add commit steps.
- Do not use `@mui/x-charts-pro` or `@mui/x-charts-premium`.
- Use a compact MUI Table matrix for the confusion matrix because Community 9.10.0 does not export `Heatmap`.
- Do not add a chart compatibility wrapper or recreate ECharts' option API.
- Do not implement custom zoom/pan. Existing From/To and bucket filters remain the temporal navigation mechanism.
- Pass `skipAnimation` to every normal MUI chart for deterministic rendering and reduced-motion safety. Deliberately omit it from `SparkLineChart`: MUI X 9.10.0 hard-codes plot-animation skipping internally, while the public prop leaks toward its hidden SVG.
- Do not use color as the only anomaly or outlier distinction.
- Use stable outer semantic chart wrappers with visible/table alternatives. Disable chart-internal keyboard navigation because accessibility proxies would otherwise add redundant tab stops inside those wrappers; configure SparkLines through typed `MuiChartsDataProvider.defaultProps.disableKeyboardNavigation` theme defaults because their direct public prop is broken in MUI X 9.10.0. Preserve existing buttons and dialog focus behavior.
- Run verification sequentially with constrained resources. Use at most two Vitest workers.

## Verification command prefix

Run frontend commands from `frontend/` with:

```bash
taskset -c 0,1 nice -n 10 ionice -c2 -n7 env NODE_OPTIONS="--max-old-space-size=2048"
```

For example:

```bash
taskset -c 0,1 nice -n 10 ionice -c2 -n7 env NODE_OPTIONS="--max-old-space-size=2048" npm test -- --run --maxWorkers=2 --no-file-parallelism
```

---

## Task 1: Install MUI X Charts and prove the required Community renderer imports

**Files:**

- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `frontend/src/theme/theme.ts`
- Create: `frontend/src/components/charts/muiChartsImports.test.ts`

### Step 1: Add a failing import-surface test

Create `frontend/src/components/charts/muiChartsImports.test.ts`:

```ts
import { describe, expect, it } from 'vitest';

describe('MUI X Charts Community import surface', () => {
  it('provides every renderer needed by this frontend', async () => {
    const [bar, line, scatter, sparkline] = await Promise.all([
      import('@mui/x-charts/BarChart'),
      import('@mui/x-charts/LineChart'),
      import('@mui/x-charts/ScatterChart'),
      import('@mui/x-charts/SparkLineChart'),
    ]);

    expect(bar.BarChart).toBeTypeOf('function');
    expect(line.LineChart).toBeTypeOf('function');
    expect(scatter.ScatterChart).toBeTypeOf('function');
    expect(sparkline.SparkLineChart).toBeTypeOf('function');
  });
});
```

Run it before installing the dependency and confirm that it fails because `@mui/x-charts` cannot be resolved:

```bash
taskset -c 0,1 nice -n 10 ionice -c2 -n7 env NODE_OPTIONS="--max-old-space-size=2048" npm test -- --run src/components/charts/muiChartsImports.test.ts --maxWorkers=1 --no-file-parallelism
```

### Step 2: Install the exact Community package version

```bash
npm install @mui/x-charts@9.10.0
```

Do not remove ECharts yet. The existing charts must keep working while feature slices migrate.

### Step 3: Re-run the import-surface test

Run the same targeted command. Expected result: one passing test and successful resolution of every chart renderer used by the Community-only migration.

### Step 4: Add type-safe theme augmentation

Add the type-only Charts augmentation beside the existing Data Grid augmentation in `frontend/src/theme/theme.ts`, then configure the typed SparkLine workaround through `MuiChartsDataProvider.defaultProps.disableKeyboardNavigation`:

```ts
import type {} from '@mui/x-data-grid/themeAugmentation';
import type {} from '@mui/x-charts/themeAugmentation';
```

Inspect the installed package before adding any runtime provider. Add `ChartsProvider` only if the actual rendered components require it; otherwise skip it. Do not pass `disableKeyboardNavigation` directly to `SparkLineChart`.

Run the frontend build after the theme augmentation and any required provider change:

```bash
taskset -c 0,1 nice -n 10 ionice -c2 -n7 env NODE_OPTIONS="--max-old-space-size=2048" npm run build
```

---

## Task 2: Add a small shared MUI chart presentation layer

**Files:**

- Create: `frontend/src/components/charts/muiChartTheme.ts`
- Create: `frontend/src/components/charts/muiChartTheme.test.ts`
- Modify only if needed: `frontend/src/components/charts/ChartFrame.tsx`

### Step 1: Write tests for shared colors and numeric formatters

The shared module should contain only renderer-neutral constants and formatting functions used by multiple feature slices:

```ts
import { createTheme } from '@mui/material/styles';
import { describe, expect, it } from 'vitest';
import { formatChartNumber, getChartColors } from './muiChartTheme';

describe('muiChartTheme', () => {
  it('derives semantic series colors from the active MUI theme', () => {
    const theme = createTheme();
    const chartColors = getChartColors(theme);

    expect(chartColors.temperature).toBe(theme.palette.primary.main);
    expect(chartColors.humidity).toBe(theme.palette.success.main);
    expect(chartColors.anomaly).toBe(theme.palette.error.main);
    expect(chartColors.threshold).toBe(theme.palette.warning.main);
  });

  it('formats finite values and rejects non-finite display values', () => {
    expect(formatChartNumber(12.345, 2)).toBe('12.35');
    expect(formatChartNumber(Number.NaN, 2)).toBe('—');
  });
});
```

Run the targeted test and confirm it fails because the module does not exist.

### Step 2: Implement only the shared primitives

Create `muiChartTheme.ts` with:

- a `getChartColors(theme)` function deriving temperature, humidity, anomaly score, threshold, normal-point, and outlier colors from the active MUI palette;
- `formatChartNumber(value, precision)`;
- shared compact axis/legend style constants only if at least two chart consumers need the exact same values.

Do not create a generic `MuiChart` wrapper. Feature components should render the MUI X component they actually use.

### Step 3: Keep `ChartFrame` renderer-agnostic

If `ChartFrame` currently assumes ECharts-specific children or sizing, minimally change it to accept ordinary React children. Preserve its title, summary, table alternative, loading, empty, and error behavior.

### Step 4: Verify the shared layer

Run the targeted tests and build. Expected result: tests pass and TypeScript resolves all shared exports without assertions or suppression comments.

---

## Task 3: Convert the temporal option builders into typed MUI data mappers

**Files:**

- Modify: `frontend/src/components/charts/temporalOptions.ts`
- Modify: `frontend/src/components/charts/options.test.ts`

### Step 1: Add tests for explicit MUI-oriented output

Keep the existing domain input type. Replace tests that assert ECharts option internals with tests for stable typed data:

```ts
expect(buildTemporalChartData(rows)).toEqual({
  xAxis: expect.any(Array),
  temperature: expect.any(Array),
  humidity: expect.any(Array),
  anomalyScore: expect.any(Array),
  threshold: expect.any(Array),
  anomalyPointIndexes: expect.any(Array),
});
```

Add focused assertions that:

- all series preserve the same row order;
- timestamps are represented consistently as `Date` or epoch milliseconds;
- missing numeric values remain `null` rather than becoming zero;
- anomaly indexes match the original rows;
- sparkline data is split into independent temperature and humidity arrays.

Run the temporal mapper tests and confirm the new assertions fail against the ECharts option output.

### Step 2: Implement the minimum mapper API

Export typed functions such as:

```ts
export type TemporalChartData = {
  xAxis: Date[];
  temperature: Array<number | null>;
  humidity: Array<number | null>;
  anomalyScore: Array<number | null>;
  threshold: Array<number | null>;
  anomalyPointIndexes: number[];
};

export type SensorSparklineData = {
  temperature: number[];
  humidity: number[];
};

export function buildTemporalChartData(rows: SensorReading[]): TemporalChartData;
export function buildSensorSparklineData(rows: SensorReading[]): SensorSparklineData;
```

Reuse existing normalization and summary logic. Delete only the ECharts option assembly from this module.

### Step 3: Preserve current empty and invalid-input semantics

Strict Zod API-contract boundaries reject malformed or non-finite numeric payloads before mappers. Mapper tests cover already-validated nullable, empty, and gap cases; chart components do not clean domain data.

### Step 4: Verify the mapper

Run:

```bash
taskset -c 0,1 nice -n 10 ionice -c2 -n7 env NODE_OPTIONS="--max-old-space-size=2048" npm test -- --run src/components/charts/options.test.ts --maxWorkers=1 --no-file-parallelism
```

Expected result: all temporal mapper tests pass.

---

## Task 4: Migrate Overview sensor cards to two separate MUI sparklines

**Files:**

- Modify: `frontend/src/features/overview/SensorMatrix.tsx`
- Modify: `frontend/src/pages/OverviewPage.test.tsx`
- Modify if selectors require it: `frontend/tests/e2e/overview.spec.ts`

### Step 1: Add failing behavior tests

For each populated sensor card, assert:

- a visible `Temperature` label;
- one chart with an accessible label containing the sensor name and `temperature`;
- a visible `RH` label;
- one chart with an accessible label containing the sensor name and `humidity`;
- existing latest-value, status, alert, and navigation behavior remains present;
- loading and no-data cards do not render misleading charts.

Prefer role/name queries over canvas or SVG implementation selectors.

### Step 2: Render two `SparkLineChart` components

Use direct imports:

```ts
import { SparkLineChart } from '@mui/x-charts/SparkLineChart';
```

Render independent series from `buildSensorSparklineData`. Keep them compact and visually subordinate to the primary sensor status. Do not merge Temperature and RH into one chart because their units and scales differ.

Each sparkline must have:

- a stable accessible label;
- `showTooltip` only if it does not break touch behavior;
- a semantic series color;
- no axis chrome;
- no zoom controls.

Deliberately omit `skipAnimation` and the direct `disableKeyboardNavigation` prop from `SparkLineChart`: MUI X 9.10.0 already skips its plot animation internally, `skipAnimation` leaks toward its hidden SVG, and direct keyboard-navigation configuration is broken. The typed provider theme default from Task 1 disables SparkLine keyboard proxies.

### Step 3: Keep the current card layout behavior

Preserve the completed desktop and mobile dashboard redesign. Do not change the sidebar, card navigation, alert badges, or touch target sizes while migrating charts.

### Step 4: Verify Overview

Run the component tests, then the Overview Playwright test:

```bash
taskset -c 0,1 nice -n 10 ionice -c2 -n7 env NODE_OPTIONS="--max-old-space-size=2048" npm test -- --run src/pages/OverviewPage.test.tsx --maxWorkers=1 --no-file-parallelism
taskset -c 0,1 nice -n 10 ionice -c2 -n7 env NODE_OPTIONS="--max-old-space-size=2048" npm run test:e2e -- tests/e2e/overview.spec.ts
```

Expected result: both sparkline labels are discoverable, active-anomaly assertions confirm all 12 Overview chart wrappers contain no tabbable proxy descendants, and all existing Overview behavior still passes.

---

## Task 5: Migrate shared temporal panels to three MUI line charts

**Files:**

- Modify: `frontend/src/features/sensors/SensorHistoryPanel.tsx`
- Modify: `frontend/src/pages/SensorDetailPage.test.tsx`
- Modify: `frontend/src/features/eda/TemporalPatternsPanel.tsx`
- Modify: `frontend/src/pages/EdaPage.test.tsx`

### Step 1: Add failing panel tests

For each panel, assert three separately titled chart regions:

1. Temperature history.
2. Relative humidity history.
3. Anomaly score and threshold.

Also assert that:

- existing From/To and bucket filters remain usable;
- loading, empty, and error states render before chart construction;
- the existing accessible table alternative still exposes the same rows and columns;
- the anomaly chart contains both Score and Threshold series.

### Step 2: Render `LineChart` directly

Use direct imports:

```ts
import { LineChart } from '@mui/x-charts/LineChart';
```

Map `TemporalChartData` into three charts with a shared time axis contract. Use an explicit axis `scaleType` supported by the installed package, set every time axis `min` and `max` from the selected From and To values, set `skipAnimation`, and preserve null gaps instead of interpolating missing values.

The third chart must use distinct semantic styles for Score and Threshold and must mark anomaly intervals with a composed SVG overlay or equivalent non-color-only positional markers. The table remains an accessible textual equivalent, not a substitute for the visual non-color-only distinction. If the installed Community APIs cannot support the approved overlay contract, stop and report the boundary rather than silently dropping anomaly markers.

### Step 3: Preserve filtering as the navigation model

Do not add MUI zoom props. The From/To and bucket controls remain the supported way to change the visible range.

### Step 4: Verify both consumers

Run both targeted test files, then the related sensor and EDA page tests. Expected result: three chart regions per panel and unchanged filter/table behavior.

---

## Task 6: Convert EDA builders and consumers to BarChart and ScatterChart

**Files:**

- Modify: `frontend/src/components/charts/edaOptions.ts`
- Modify: `frontend/src/components/charts/options.test.ts`
- Modify: `frontend/src/features/eda/DistributionPanel.tsx`
- Modify: `frontend/src/pages/EdaPage.test.tsx`
- Modify: `frontend/src/features/eda/CorrelationPanel.tsx`
- Modify: `frontend/src/pages/EdaPage.test.tsx`

### Step 1: Replace option-shape tests with domain-data tests

Define small typed outputs:

```ts
export type HistogramChartData = {
  labels: string[];
  counts: number[];
};

export type CorrelationPoint = {
  id: string;
  x: number;
  y: number;
  anomalous: boolean;
};
```

Tests must cover bin order, count totals, point identity, anomaly classification, and already-validated empty input. Strict Zod API-contract tests cover malformed and non-finite payload rejection before mappers.

Run the mapper tests and confirm they fail against the current ECharts option builders.

### Step 2: Implement renderer-neutral mappers

Keep existing histogram and correlation calculations. Remove tooltip formatter functions and ECharts series/axis configuration from `edaOptions.ts`.

### Step 3: Migrate `DistributionPanel`

Render `BarChart` directly from the histogram labels/counts with `skipAnimation`. Preserve the panel title, summary, and table alternative. Use category labels from the mapper; do not reconstruct bins in the component.

### Step 4: Migrate `CorrelationPanel`

Render `ScatterChart` with `skipAnimation`, circular Normal markers, and alarm-colored diamond Anomaly markers. Use documented chart composition where required for marker shape; color alone is not sufficient. Preserve point IDs so tooltips and tests can identify records consistently.

### Step 5: Verify EDA

Run the mapper and both panel tests, then the EDA page-level tests. Expected result: no ECharts import remains in the EDA feature slice.

---

## Task 7: Convert evaluation builders and consumers to a MUI Table matrix and LineChart

**Files:**

- Modify: `frontend/src/components/charts/evaluationOptions.ts`
- Modify: `frontend/src/components/charts/options.test.ts`
- Modify: `frontend/src/features/modelEvaluation/LabeledMetricsPanels.tsx`
- Modify: `frontend/src/pages/ModelEvaluationPage.test.tsx`

### Step 1: Add failing data-mapper tests

Define outputs for the three evaluation visualizations:

```ts
export type ConfusionMatrixChartData = {
  xLabels: string[];
  yLabels: string[];
  rows: Array<{ actual: string; counts: number[] }>;
  maxCount: number;
};

export type EvaluationCurvePoint = {
  x: number;
  y: number;
};
```

Tests must verify:

- confusion-matrix cell coordinates and values;
- preserved class-label order;
- ROC point order and the diagonal reference series;
- precision–recall point order;
- already-validated empty input handling; strict Zod API-contract tests cover malformed and non-finite payload rejection before mappers.

### Step 2: Implement renderer-neutral evaluation data

Reuse the current backend response mapping. Remove ECharts heatmap and line option construction.

### Step 3: Migrate the confusion matrix to a compact MUI Table matrix

Render the mapper output with existing MUI Table primitives. Use Predicted labels as column headers, Actual labels as row headers, and keep every count visible. Derive cell background intensity from `count / maxCount` using the active theme; choose foreground text from the theme for sufficient contrast. Preserve the existing accessible description and bounded data dialog. Do not introduce a reusable heatmap abstraction or another visualization dependency.

### Step 4: Migrate ROC and precision–recall curves

Render each with `LineChart` and `skipAnimation`. Preserve curve labels, axis labels, and the ROC diagonal reference. Style that diagonal as dashed with the public `lineClasses.line` plus stable `[data-series="roc-reference-series"]`. Do not enable zoom.

### Step 5: Verify evaluation panels

Run mapper and panel tests, then model-evaluation page tests. Expected result: all three visualizations render and no ECharts import remains in the feature slice.

---

## Task 8: Delete the ECharts layer and enforce migration completeness

**Files:**

- Delete: `frontend/src/components/charts/EChart.tsx`
- Delete: `frontend/src/components/charts/EChart.test.tsx`
- Delete: `frontend/src/theme/echartsTheme.ts`
- Delete: `frontend/src/theme/echartsTheme.test.ts`
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Create: `frontend/src/components/charts/noEcharts.test.ts`
- Modify any remaining barrel exports that reference deleted files.

### Step 1: Add a migration-completeness test

Create a small source scan test that fails when application source files still import ECharts packages or the deleted wrapper. Exclude `node_modules`, generated files, and the test itself. The test should reject these patterns:

- imports from `echarts`;
- imports from `echarts-for-react`;
- imports of `components/charts/EChart`;
- imports of `theme/echartsTheme`.

Use Node standard-library filesystem APIs; do not add a dependency for source scanning.

### Step 2: Confirm the completeness test fails

Run it before deletion. Expected result: it reports the remaining ECharts files/imports.

### Step 3: Remove ECharts runtime code and dependencies

Delete the wrapper/theme files and remove the ECharts package entries from `package.json` with npm so the lockfile stays consistent:

```bash
npm uninstall echarts
```

If another explicit ECharts package exists, remove it only after confirming no consumer remains.

### Step 4: Clean stale exports and tests

Remove barrel exports and test fixtures that exist only for ECharts. Do not delete domain mapper coverage added in earlier tasks.

### Step 5: Re-run the completeness test

Expected result: it passes and application code contains no ECharts import.

---

## Task 9: Full regression, build, production, accessibility, and visual verification

**Files:**

- Modify only when an assertion is invalidated by the intentional renderer change: `frontend/tests/e2e/*.spec.ts`
- Update visual baselines only after inspecting each diff: `frontend/test-results/**` or the project's existing screenshot location.

### Step 1: Run all unit/component tests

```bash
taskset -c 0,1 nice -n 10 ionice -c2 -n7 env NODE_OPTIONS="--max-old-space-size=2048" npm test -- --run --maxWorkers=2 --no-file-parallelism
```

Expected result: all tests pass. Existing intentional skips may remain; do not add new skips to hide migration failures.

### Step 2: Run lint

```bash
taskset -c 0,1 nice -n 10 ionice -c2 -n7 env NODE_OPTIONS="--max-old-space-size=2048" npm run lint
```

Expected result: exit code 0 and no new warnings. The pre-existing generated `public-dev/mockServiceWorker.js` warning may remain.

### Step 3: Run the production build

```bash
taskset -c 0,1 nice -n 10 ionice -c2 -n7 env NODE_OPTIONS="--max-old-space-size=2048" npm run build
```

Expected result: exit code 0, no unresolved chart imports, and no ECharts chunk in the build output.

### Step 4: Run production integration verification

```bash
taskset -c 0,1 nice -n 10 ionice -c2 -n7 env NODE_OPTIONS="--max-old-space-size=2048" npm run test:production
```

Expected result: exit code 0.

### Step 5: Run Playwright sequentially

Run the existing layout, Overview, EDA, sensor-detail, model-evaluation, accessibility, and visual specs one file at a time. Do not increase parallelism.

At minimum verify:

- desktop Overview cards show both Temperature and RH sparklines;
- the 390px mobile rail and card layout remain intact;
- temporal pages show three line-chart panels and working filters;
- EDA histogram and scatter views preserve tables and empty states;
- confusion matrix, ROC, and precision–recall views remain readable;
- keyboard and accessible-name checks pass;
- active-anomaly assertions confirm all 12 Overview chart wrappers contain no tabbable proxy descendants;
- no console errors originate from MUI chart sizing or invalid data.

### Step 6: Inspect visual diffs before accepting baselines

Renderer changes will alter chart pixels. Update a baseline only when layout, labels, color contrast, and data semantics are correct. Do not bulk-accept screenshots.

### Step 7: Final source and dependency checks

Run:

```bash
npm ls @mui/x-charts echarts
```

Expected result:

- `@mui/x-charts@9.10.0` is installed;
- ECharts is absent;
- the migration-completeness test passes;
- no deleted wrapper/theme import remains.

---

## Done criteria

The migration is complete only when all of the following are true:

- Every Overview sensor card has separate Temperature and RH MUI sparklines.
- Sensor Detail and EDA temporal history use three MUI line charts.
- EDA distribution uses `BarChart` and correlation uses `ScatterChart`.
- Confusion matrix uses an accessible MUI Table matrix; ROC and precision–recall use `LineChart`.
- Existing filters, summaries, tables, loading/empty/error states, routes, alerts, and accessibility remain functional.
- Every normal MUI chart sets `skipAnimation`; SparkLines deliberately omit the leaking public prop while retaining MUI X 9.10.0's internal plot-animation skip; anomaly/outlier state is never communicated by color alone.
- No custom zoom/pan or generic chart compatibility wrapper was added.
- `EChart.tsx`, `echartsTheme.ts`, and ECharts dependencies are gone.
- Targeted tests, full tests, lint, build, production verification, Playwright, and visual QA pass.

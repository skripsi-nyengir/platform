# MUI X Charts full migration design

## Purpose

Replace every frontend ECharts visualization with MUI X Charts 9.10.0 while preserving the application's validated API contracts, data bounds, error states, table alternatives, routes, and keyboard behavior. The Overview sensor cards also adopt the supplied reference layout: Temperature and RH each receive their own compact sparkline inside the existing metric tile.

This is a rendering migration, not a data-contract redesign. No backend, query, schema, mock payload, or alert lifecycle behavior changes.

## Approved decisions

- Migrate all chart-bearing pages in one implementation: Overview, Sensor Detail, EDA, and Model Evaluation.
- Use the MIT-licensed Community package `@mui/x-charts` version `9.10.0`, aligned with `@mui/x-data-grid` 9.10.0 and Material UI 9.2.0.
- Do not add MUI X Pro or Premium.
- Render the confusion matrix as an accessible MUI Table matrix because the published Community 9.10.0 artifact does not export `Heatmap`, despite the versioned documentation showing it.
- Remove chart-internal zoom and pan. Existing From/To and bucket controls remain the only temporal-range controls.
- Remove `echarts` after the final ECharts consumer, wrapper, theme adapter, and option builder are gone.
- Use MUI's self-contained chart components by default. Use composition only when required for anomaly overlays or non-color-only outlier distinction.
- Pass `skipAnimation` to normal MUI chart components for deterministic rendering and reduced-motion safety. In MUI X 9.10.0, `SparkLineChart` internally hard-codes plot-animation skipping; passing the public prop leaks it toward the hidden SVG, so SparkLine usage deliberately omits it.

## Dependency and theme integration

Add `@mui/x-charts@9.10.0` as a production dependency. Add the type-only `@mui/x-charts/themeAugmentation` import beside the existing Data Grid augmentation so chart defaults and overrides remain type-safe.

Reuse the existing MUI palette and typography. Temperature uses the current primary blue, RH uses the current success teal, anomaly score uses warning, and candidate outliers use alarm red plus a distinct marker shape. Chart axes, grid lines, legends, tooltips, and overlays derive colors from the active MUI theme rather than hardcoded light-theme defaults. Configure `MuiChartsDataProvider.defaultProps.disableKeyboardNavigation` through the typed theme so SparkLines disable keyboard navigation without using their broken direct prop.

No generic compatibility layer translates ECharts option objects. The migration replaces imperative ECharts options with typed MUI props and small pure data mappers.

## Chart mapping

### Overview sensor matrix

Each of the six sensor cards keeps its current values, status, metadata, inference state, links, and chart-state fallbacks.

The current combined 90 px EChart is replaced by two independent `SparkLineChart` components inside the Temperature and RH metric tiles, matching the supplied reference. Each sparkline:

- uses the existing bounded 30-minute raw history query;
- receives one numeric series and matching `Date` x-axis values;
- uses the metric's existing color and unit;
- has no visible axes, legend, toolbar, or zoom control;
- uses a fixed tile height that does not shift loading, empty, error, or valid states;
- preserves the visible numeric value as the primary accessible telemetry presentation.

The history query remains one request per sensor, not one request per metric.

### Sensor Detail and EDA temporal patterns

The shared temporal rendering becomes a three-panel MUI chart stack using aligned time data:

1. Temperature line;
2. Relative humidity line;
3. Anomaly score and threshold.

The panels share identical From/To bounds and aligned `Date` values. Every time axis explicitly sets `min` and `max` from the selected From and To values. Missing telemetry remains `null`; documented gaps are not connected. The score panel keeps the threshold visible and marks anomaly intervals with a custom composed SVG overlay or equivalent non-color-only markers. The existing textual temporal summary and bounded data dialog remain unchanged.

Chart-internal wheel, drag, pinch, and slider zoom are intentionally removed. The existing From, To, bucket, and sensor controls provide range selection. No replacement local zoom state is introduced.

### EDA distributions

Each histogram becomes a `BarChart` using the API-provided bins. Bin labels are derived from `[start, end)` bounds, the x-axis uses a band scale, adjacent bars have no categorical gap, and counts use the current primary color. The sample count, summary statistics, bin control, and `Lihat data` dialog remain unchanged.

### EDA correlation

The correlation plot becomes a `ScatterChart` with two stable series:

- observations: standard circular markers;
- candidate outliers: alarm-colored diamond markers.

Axes retain the selected field names. Correlation, displayed sample count, total sample count, and candidate count remain available in text and the bounded table dialog. Candidate status is conveyed by label and marker shape, not color alone.

### Model Evaluation confusion matrix

The confusion matrix becomes a compact MUI Table matrix. Columns remain Predicted, rows remain Actual, and every cell keeps its count visible. Cell background intensity derives from the active MUI palette, while text contrast remains readable at every value. Class labels, orientation, accessible description, and the existing bounded data alternative remain unchanged. This avoids a paid package and removes the final ECharts consumer without recreating a generic chart layer.

### ROC and Precision–Recall

ROC and Precision–Recall become `LineChart` components with fixed 0–1 axes, stable series IDs, hidden point marks, and explicit labels. ROC includes its reference diagonal as a separate dashed line series styled with the public `lineClasses.line` plus stable `[data-series="roc-reference-series"]`. AUC and average precision remain visible outside the chart and in their existing bounded data alternatives.

## Shared data mappers

Keep transformations pure and specific to the required chart family:

- telemetry points to aligned `Date[]`, temperature `(number | null)[]`, and RH `(number | null)[]`;
- inference windows to score points, threshold, and anomaly intervals;
- histogram bins to labels and counts;
- correlation points to observation and candidate-outlier series;
- confusion matrix to labeled row/column cells and a maximum count used for color intensity;
- ROC and Precision–Recall points to aligned x/y arrays.

Strict Zod API-contract boundaries reject malformed or non-finite numeric payloads before they reach mappers. Mapper tests cover already-validated nullable, empty, and gap cases rather than duplicating trust-boundary validation.

Do not create a universal chart-config abstraction. Reuse a mapper only where existing pages already share the same domain transform, especially Sensor Detail and EDA temporal patterns.

## Accessibility and interaction

- Represent chart content with stable outer semantic wrappers plus visible/table alternatives.
- Disable chart-internal keyboard navigation because MUI accessibility proxies become redundant tab stops inside those wrappers. For SparkLines, apply the typed `MuiChartsDataProvider.defaultProps.disableKeyboardNavigation` theme configuration because the direct public prop is broken in MUI X 9.10.0.
- Keep visible units, metric labels, current values, status Chips, and table alternatives.
- Do not rely on color alone for anomaly state, outliers, health, or series identity.
- Keep every `Lihat data` dialog, its pagination, focus trap, focus restoration, and existing button behavior.
- Preserve existing loading, empty, initial-error, and retained-data/refetch-error states without hiding non-chart content.
- Tooltips remain scoped to chart containers and format values with their units.

## Removal boundary

Delete the following only after every call site has migrated and all focused tests pass:

- `src/components/charts/EChart.tsx` and its lifecycle test;
- `src/theme/echartsTheme.ts`;
- ECharts option builders in `temporalOptions.ts`, `edaOptions.ts`, and `evaluationOptions.ts` after useful summary/data transforms have moved to MUI-specific mapper modules;
- the `echarts` package and lockfile entries.

No ECharts dependency, import, type, option object, wrapper, or theme adapter remains at completion.

## Verification

### Unit and component tests

- Test every mapper with already-validated normal, null, gap, empty, boundary, and outlier data.
- Assert Overview renders twelve MUI sparkline wrappers from six sensor history results while retaining all fallback states, and that the active-anomaly assertion confirms all 12 Overview chart wrappers contain no tabbable proxy descendants.
- Assert temporal panels preserve three semantic metrics, threshold, anomaly information, and bounded table access.
- Assert histogram, scatter, MUI Table matrix, ROC, and Precision–Recall labels, axes, series, counts, and accessible names.
- Replace EChart lifecycle and option-object tests with MUI chart component and mapper tests.
- Keep contract, API, query, alert lifecycle, and bounded-dialog tests unchanged unless import paths move.

### Browser verification

- Exercise existing buttons and table-dialog keyboard workflows, including dialog focus trapping and restoration.
- Verify Overview, Sensor Detail, EDA, and Model Evaluation at mobile, 1280, 1440, and 1920 widths with no horizontal overflow or clipping.
- Update visual baselines only after direct inspection confirms intentional MUI rendering differences.
- Run dual visual QA against the supplied reference and the current approved dark industrial design.

### Quality gates

Run diagnostics on every changed TypeScript file, focused tests after each chart family, the full unit suite, chart-bearing E2E specs, layout and visual suites, lint, production build, and production-artifact verification. Commands remain sequential and resource-limited.

## Out of scope

- Backend or API changes;
- new filters, routes, actions, dashboard top bars, or report controls from the reference image;
- MUI X Pro/Premium licensing;
- custom zoom/pan replacement;
- chart export or download;
- redesigning non-chart page content.

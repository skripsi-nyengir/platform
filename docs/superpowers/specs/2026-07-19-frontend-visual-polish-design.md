# Frontend Visual Polish Design

**Date:** 2026-07-19  
**Status:** Approved design  
**Scope:** Route-first visual redesign of the existing React 19 and MUI 9 frontend

## Background

The frontend is functionally complete, but its presentation has four recurring problems:

1. The page canvas stretches too far on wide screens and uses undersized gutters.
2. A 4px spacing base is used with values that produce cramped 8–12px surfaces.
3. The current 20/16/14px heading scale and repeated `body2` treatment create weak hierarchy and make pages feel text-heavy.
4. `body.minWidth: 1280px` causes document-level horizontal scrolling in a headed browser at an exact 1280px viewport because the vertical scrollbar reduces the usable client width to 1265px.

The redesign is route-first: each page receives a composition suited to its information. Shared typography, spacing, shell, and state rules remain global so the six routes stay coherent.

## Goals

- Establish a balanced operational-dashboard aesthetic with clearer hierarchy and calmer density.
- Keep every existing explanation, label, value, action, and accessibility affordance visible.
- Refine the fixed desktop sidebar without adding collapse behavior.
- Give charts, tables, filters, cards, and prose predictable spacing and width rules.
- Eliminate document-level horizontal scrolling at headed 1280, 1440, and 1920px viewports.
- Preserve all domain behavior, API contracts, URL state, keyboard behavior, and test intent.

## Non-goals

- No mobile redesign or temporary drawer variant.
- No domain, API, query, mutation, or routing changes.
- No hidden explanatory content, hover-only definitions, accordions, or truncation.
- No new animation library or decorative motion system.
- No generic design-system rewrite or speculative component abstraction.
- No migration from ECharts to MUI X Charts in this work. That migration is a separate follow-up after visual polish passes acceptance.

## Approved Direction

- **Visual character:** balanced dashboard: operational and technical, but not cramped.
- **Implementation approach:** route-first redesign supported by a small shared visual foundation.
- **UI and prose font:** Inter.
- **Technical-value font:** IBM Plex Mono.
- **Sidebar:** fixed and refined at desktop widths.
- **Text:** all explanatory content remains visible.
- **Content width:** hybrid; charts and tables are fluid while prose and metadata have readable line lengths.
- **Charts:** retain ECharts 6.1.0 for this polish; evaluate MUI X Charts separately afterward.

## Shared Visual Foundation

### Typography

Use Inter for navigation, headings, controls, labels, and explanatory prose. Add `@fontsource/inter` through the same self-hosted font-loading pattern already used by the application.

Use IBM Plex Mono only for:

- sensor, alert, request, and artifact identifiers;
- timestamps, hashes, and versions;
- measurements, thresholds, scores, and metric values;
- chart axes and tooltip values;
- numeric and technical Data Grid cells.

Use this type scale:

| Role | Size / line height |
|---|---|
| Page title | 28 / 32px |
| Section title | 18 / 24px |
| Panel title | 15 / 20px |
| Body | 14 / 20px |
| Supporting text | 13 / 18px |
| Caption | 12 / 16px |

Long hashes, timestamps, and identifiers must wrap or break safely. They must never widen a route or the document.

### Spacing and Rhythm

Retain the existing 4px base token, but standardize composition around:

- 8px for tightly related metadata and control gaps;
- 16px for surface padding and normal component gaps;
- 24px between major page sections;
- 24px route gutters at the exact 1280px desktop target;
- 32px route gutters from 1440px upward.

### Width and Surfaces

- Center the route canvas and cap it at 1600px.
- Let tables and charts consume the available route width.
- Cap explanatory prose at approximately 68 characters.
- Cap metadata groups at approximately 84 characters.
- Continue using outlined MUI `Paper` for semantic sections.
- Avoid double-outline nesting. Internal subdivisions use dividers or restrained neutral/signal backgrounds.
- Keep repeated domain entities such as alerts, sensors, and anomaly candidates as cards.

No new shared layout abstraction is required. Global rules belong in the existing tokens and theme; route-specific composition remains in existing pages and feature components.

## Application Shell and Sidebar

Keep the permanent, full-height 264px MUI Drawer. Do not add collapse, compact, temporary, or automatic responsive variants.

Retain the existing navigation groups and destinations:

- **Operations:** Overview, Sensors, Alerts
- **Analysis:** EDA, Model Evaluation
- **System:** System Health

Navigation rows remain 44px high. Group labels use uppercase Inter with restrained letter spacing and 24px separation between groups. The active destination retains the teal rail, dark active fill, high-contrast text, `NavLink` behavior, and `aria-current`. Hover must remain visually quieter than active state.

The main shell flex child and all nested grid/flex children capable of holding charts, tables, hashes, or timestamps use `min-width: 0`.

## Route Designs

### Overview (`/`)

Composition:

1. Page header
2. Four-part operational summary
3. Attention queue
4. Sensor matrix

The operational summary remains one row at exact 1280. Alert cards keep their red priority rail and lifecycle actions. Sensor cards separate status, measurements, inference, and actions into distinct visual tiers instead of repeated body text. The sensor matrix uses a bounded auto-fit layout with a 320px minimum: two columns at exact 1280 and three only when space permits.

### Sensor Detail (`/sensors/:sensorId`)

Composition:

1. Sensor identity and metadata
2. Wrapping temporal filters
3. Current snapshot
4. Full-width telemetry and inference history
5. Related immutable events

History count summaries become lightweight paired blocks instead of nested cards. The ECharts timeline remains full-width and retains its explanation and data dialog. Related events use a divided list or responsive card grid while preserving actor, note, window, and timestamp text.

### Alerts (`/alerts`)

Composition:

1. Page header
2. Wrapping filter toolbar
3. Full-width MUI X Data Grid
4. Selected alert immutable event history

Sensor, status, and date controls receive stable widths and wrap instead of colliding. Preserve server pagination, keyboard and row selection, action columns, pending states, 409 conflict handling, unchanged-command retry behavior, and selected-alert history.

### EDA (`/eda`)

Composition:

1. Filter surface
2. Quality/coverage and missingness row
3. Distribution panels
4. Temporal patterns
5. Correlation
6. Sensor comparison
7. Candidate outliers

Distribution panels use a 320px minimum: two columns at exact 1280 and three on wider desktops. Temporal and correlation charts remain full-width. Explanatory statements stay directly below their headings. Every chart retains a consistently aligned **Lihat data** action.

### Model Evaluation (`/model-evaluation`)

Composition:

1. Compact version selector
2. Artifact identity and metadata
3. Scalar metric grid
4. Labeled evaluation charts
5. Notes

Artifact metadata uses two columns, with hashes in IBM Plex Mono and safe wrapping. Confusion matrix, ROC, and precision-recall panels use a bounded auto-fit grid with a 420px minimum: two columns at exact 1280 and three only on genuinely wide route canvases. Add visible panel headings while preserving current chart ARIA labels and bounded data dialogs.

### System Health (`/system-health`)

Composition:

1. Page header and readable-width explanation
2. Two-column freshness snapshot
3. Full-width service table

Preserve the distinction between liveness, readiness, poll freshness, and telemetry freshness. Semantic chips may reinforce statuses, but the original status text remains visible. Service details and timestamps remain visible, with technical values in IBM Plex Mono.

## Shared Components and States

### Charts

- Keep ECharts 6.1.0 and existing ResizeObserver-based width behavior.
- Use Inter for visible titles and legends.
- Use IBM Plex Mono for axes, tooltip values, measurements, and thresholds.
- Preserve `role="img"`, accessible names, explanatory copy, and every bounded **Lihat data** alternative.

### Tables and Data Grid

- Use full-width framed surfaces with clearer header contrast.
- Apply IBM Plex Mono only to technical columns.
- Preserve native MUI X `grid` and `gridcell` semantics.
- Preserve server pagination, row selection, bounded counts, and keyboard behavior.

### Filters and Actions

- Toolbars wrap within route width rather than forcing document width.
- Keep related controls grouped and labels visible.
- Do not introduce sticky, floating, or hidden actions.

### Loading, Empty, and Error States

- Keep visible loading labels and non-animated skeletons.
- Reserve approximately the final panel footprint to reduce layout shift.
- Keep empty states as visible title-and-explanation blocks with `role="status"` where currently used.
- Keep initial error title, detail, request ID, and Retry action.
- Show refresh failures above retained stale data; never replace stale content or present it as current.

### Mutation and Dialog States

- Preserve pending, disabled, success, conflict, unchanged-command retry, and failure behavior.
- Preserve MUI dialog focus trapping, Escape and Close behavior, focus restoration, bounded row counts, titles, and `maxWidth="lg"`.
- Status chips may supplement visible text but never replace it.

## Exact-1280 Layout Contract

The current document-level `body.minWidth: 1280px` must be removed. Do not hide the defect with `overflow-x: hidden`.

At the failing headed-browser case:

- client width is approximately 1265px after the vertical scrollbar;
- the fixed sidebar consumes 264px;
- 24px gutters leave approximately 953px of route content.

All page compositions must fit that real client width through:

- `min-width: 0` on flex/grid children;
- `minmax(0, 1fr)` for fractional grid columns;
- bounded auto-fit layouts for card/chart collections;
- wrapping filter and action rows;
- safe wrapping for technical values;
- fluid ECharts containers.

Horizontal scrolling is permitted only inside an inherently wide `TableContainer` or Data Grid surface when unavoidable. It is forbidden on `html`, `body`, `#root`, the application shell, and route canvas.

Desktop validation targets are 1280, 1440, and 1920px. Behavior below the desktop target is outside this specification.

## Files in Scope

Expected existing files and areas include:

- `frontend/src/app/AppShell.tsx`
- `frontend/src/app/navigation.ts`
- `frontend/src/theme/tokens.ts`
- `frontend/src/theme/theme.ts`
- `frontend/src/theme/echartsTheme.ts`
- `frontend/src/main.tsx`
- the six route page components under `frontend/src/pages/`
- existing Overview, Sensor Detail, Alerts, EDA, Model Evaluation, and System Health feature components
- existing shared chart, data-dialog, filter, skeleton, empty, and error components
- existing chart option modules, including temporal, EDA, and model-evaluation options
- existing route, layout, keyboard, behavior, and visual tests

No new source-level layout abstraction is required. The only planned dependency addition is the Inter font package following the existing Fontsource pattern.

## Verification and Acceptance

### Responsive Desktop

- Exercise all six routes in headed browsers at 1280, 1440, and 1920px.
- Require `document.documentElement.scrollWidth === document.documentElement.clientWidth` at each target.
- At exact 1280, test with a vertical scrollbar present.
- Confirm no link, button, input, select, Data Grid focus cell, dialog control, chart action, explanation, hash, or timestamp is clipped.

### Typography

- Verify computed UI and prose font is Inter.
- Verify designated technical values use IBM Plex Mono.
- Verify long technical values wrap without widening the route.

### Behavior and Accessibility

- Preserve URL filters, API/query behavior, data counts, chart labels and alternatives, server pagination, alert lifecycle behavior, retry handling, and stale-data messaging.
- Exercise keyboard paths for the sidebar, filters, Data Grid selection, alert actions, chart data dialogs, Escape/Close, and focus restoration.
- Keep every chart's accessible image label and bounded data alternative.

### Automated and Visual Gates

- Run diagnostics on every changed source and test file.
- Require lint, the existing 219-test Vitest intent, build, production verification, and existing 34-test Playwright intent to pass.
- Regenerate exactly six 1440 route baselines and review every delta deliberately.
- Perform headed spot checks at 1280 and 1920 after baseline approval.
- Re-run the five final review lanes: goal, QA, code quality, security, and context mining. All must pass.

## Deferred Follow-up: MUI X Charts

After this visual polish passes acceptance, evaluate a separate ECharts-to-MUI-X-Charts migration. That work must compare chart-type coverage, accessibility, performance, bundle impact, licensing, data-dialog compatibility, and visual-baseline churn before implementation. This specification does not introduce a mixed chart stack.

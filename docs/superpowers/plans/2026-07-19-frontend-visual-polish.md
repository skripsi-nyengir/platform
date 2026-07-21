# Frontend Visual Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign all six desktop routes into a balanced MUI dashboard while preserving behavior, eliminating exact-1280 document overflow, and retaining ECharts plus every accessible data alternative.

**Architecture:** Shared font, token, theme, shell, chart, filter, dialog, and state rules are implemented first. Six route-local tasks then reshape page composition without touching API/query/domain behavior, after which one integrated browser, visual, production, Docker, and five-lane review gate validates the result.

**Tech Stack:** React 19, TypeScript 6, Vite 8, MUI Material 9.2, MUI X Data Grid 9.10, Apache ECharts 6.1, Fontsource, Vitest 4, React Testing Library, Playwright 1.61, Docker, Nginx.

## Global Constraints

- Keep exactly six routes: `/`, `/sensors/:sensorId`, `/alerts`, `/eda`, `/model-evaluation`, and `/system-health`.
- Keep the permanent 264px desktop Drawer and existing navigation destinations/groups; do not add collapse or mobile variants.
- Use Inter for UI/prose and IBM Plex Mono only for technical values.
- Keep the 4px MUI spacing base. Use 8px for tight gaps (`2` units), 16px for surface padding (`4` units), and 24px between major sections (`6` units).
- Use 24px route gutters at exact 1280 and 32px from 1440 upward; cap the centered route canvas at 1600px.
- Keep every explanation, label, value, action, status word, and accessibility affordance visible.
- Remove document-level `min-width: 1280px`; never mask overflow with `overflow-x: hidden`.
- Permit horizontal scrolling only inside an inherently wide TableContainer or Data Grid.
- Keep ECharts 6.1.0, MUI X Data Grid semantics, ResizeObserver behavior, accessible chart labels, and every bounded **Lihat data** dialog.
- Defer MUI X Charts migration to a separate follow-up after this plan passes acceptance.
- Do not alter routes, URL filters, query keys, polling, API adapters, contracts, lifecycle logic, retry payloads, or MSW behavior.
- Keep exactly six 1440 visual baselines. Do not add 1280 or 1920 screenshots.
- The workspace is not a Git repository. Do not run Git and do not add commit steps.

## File Ownership and Dependencies

| Task | Depends on | Exclusive source ownership |
|---|---|---|
| 1. Foundation and shell | None | package/font files, tokens, theme, AppShell, foundation tests, generic layout gate |
| 2. Shared presentation | Task 1 | ECharts theme/options tests, temporal filters, bounded dialog, shared status state |
| 3. Overview | Tasks 1–2 | Overview page and Overview feature UI |
| 4. Sensor Detail | Tasks 1–2 | Sensor Detail page and sensor feature UI |
| 5. Alerts | Tasks 1–2 | Alerts page and alerts-ui feature UI |
| 6. EDA | Tasks 1–2 | EDA page and EDA feature UI |
| 7. Model Evaluation | Tasks 1–2 | Model Evaluation page and feature UI |
| 8. System Health | Tasks 1–2 | System Health page and feature UI |
| 9. Integrated acceptance | Tasks 3–8 | route-specific layout assertions, six baselines, full verification |

Tasks 3–8 may run in parallel after Tasks 1–2 pass. Task 9 runs sequentially after all route tasks.

---

### Task 1: Visual Foundation, Font, Shell, and Generic Layout Gate

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json` through npm only
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/theme/tokens.ts`
- Modify: `frontend/src/theme/theme.ts`
- Modify: `frontend/src/app/AppShell.tsx`
- Create: `frontend/src/theme/theme.test.ts`
- Modify: `frontend/src/app/routes.test.tsx`
- Modify: `frontend/tests/e2e/layout.spec.ts`

**Interfaces:**
- Consumes: existing six-route shell, navigation entries, 4px spacing base, and MUI theme provider.
- Produces: `tokens.font.ui`, `tokens.font.data`, approved type/line-height tokens, `tokens.size.routeCanvas`, centered route canvas, and a generic exact-1280 layout contract used by every later task.

- [ ] **Step 1: Add failing foundation tests**

Create `frontend/src/theme/theme.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { theme } from './theme'
import { tokens } from './tokens'

describe('visual foundation theme', () => {
  it('uses the approved type scale on the 4px base', () => {
    expect(tokens.spacing.unit).toBe(4)
    expect(theme.typography.fontFamily).toBe(tokens.font.ui)
    expect(theme.typography.h1).toMatchObject({ fontSize: '1.75rem', lineHeight: '2rem' })
    expect(theme.typography.h2).toMatchObject({ fontSize: '1.125rem', lineHeight: '1.5rem' })
    expect(theme.typography.h3).toMatchObject({ fontSize: '0.9375rem', lineHeight: '1.25rem' })
    expect(theme.typography.body1).toMatchObject({ fontSize: '0.875rem', lineHeight: '1.25rem' })
    expect(theme.typography.body2).toMatchObject({ fontSize: '0.8125rem', lineHeight: '1.125rem' })
    expect(theme.typography.caption).toMatchObject({ fontSize: '0.75rem', lineHeight: '1rem' })
  })

  it('does not impose or mask document-level horizontal overflow', () => {
    const baseline = theme.components?.MuiCssBaseline?.styleOverrides
    expect(baseline).toMatchObject({
      body: { margin: 0 },
      '#root': { minWidth: 0, minHeight: '100vh' },
    })
    expect(baseline).not.toHaveProperty('body.minWidth')
    expect(baseline).not.toHaveProperty('body.overflowX')
    expect(baseline).not.toHaveProperty('html.overflowX')
  })

  it('styles shared outlined surfaces and Data Grid headers', () => {
    expect(theme.components).toMatchObject({
      MuiPaper: {
        styleOverrides: {
          outlined: { borderColor: tokens.color.rule, boxShadow: 'none' },
        },
      },
      MuiDataGrid: {
        styleOverrides: {
          root: { borderColor: tokens.color.ruleStrong },
          columnHeaderTitle: { fontWeight: 700 },
        },
      },
    })
  })
})
```

Append to the existing `describe` in `frontend/src/app/routes.test.tsx`:

```tsx
it('marks the active destination and exposes a bounded route canvas', () => {
  renderApp('/')
  const navigation = screen.getByRole('navigation', { name: 'Primary navigation' })
  expect(within(navigation).getByRole('link', { name: 'Overview' })).toHaveAttribute(
    'aria-current',
    'page',
  )

  const main = screen.getByRole('main')
  expect(main).toHaveStyle({ minWidth: '0px', paddingLeft: '24px', paddingRight: '24px' })
  const routeCanvas = main.firstElementChild
  if (!(routeCanvas instanceof HTMLElement)) throw new Error('Route canvas was not rendered')
  expect(routeCanvas).toHaveStyle({
    width: '100%',
    maxWidth: '1600px',
    minWidth: '0px',
    marginLeft: 'auto',
    marginRight: 'auto',
  })
})
```

- [ ] **Step 2: Enrich the existing parameterized layout test without adding cases**

In `frontend/tests/e2e/layout.spec.ts`, retain its six-route loop and add these selectors to the existing clipping scan:

```ts
const visibleTextSelector = [
  'h1', 'h2', 'h3', 'h4', 'p', 'li', 'dt', 'dd', 'th', 'td',
  '[role="heading"]', '[role="status"]', '[role="alert"]', '[role="img"]',
].join(',')
```

After navigation, wait for fonts and chart hosts before measuring:

```ts
await page.evaluate(async () => {
  await document.fonts.ready
})
await page.locator('[role="img"]').first().waitFor({ state: 'visible', timeout: 2_000 }).catch(() => undefined)
```

At 1280, force a real vertical-scroll allocation before measuring:

```ts
if (testInfo.project.name === 'desktop-1280') {
  await page.evaluate(() => {
    document.body.style.minHeight = 'calc(100vh + 1px)'
  })
}
```

Require the actual document metrics:

```ts
const metrics = await page.evaluate(() => ({
  client: document.documentElement.clientWidth,
  scroll: document.documentElement.scrollWidth,
  clientHeight: document.documentElement.clientHeight,
  scrollHeight: document.documentElement.scrollHeight,
}))

if (testInfo.project.name === 'desktop-1280') {
  expect(metrics.scrollHeight).toBeGreaterThan(metrics.clientHeight)
}
expect(metrics.scroll).toBe(metrics.client)
```

Keep the current control clipping check and apply the same viewport-bound calculation to `visibleTextSelector`. Do not inspect `scrollWidth > clientWidth` on wrapping text nodes because valid line wrapping can produce false positives; fail only when an element bounding box leaves the document client width/height.

- [ ] **Step 3: Run the focused tests and verify red**

Run from `frontend/`:

```bash
npm test -- src/theme/theme.test.ts src/app/routes.test.tsx
npx playwright test --config playwright.config.ts --project=desktop-1280 --headed tests/e2e/layout.spec.ts
```

Expected: theme/shell assertions fail because Inter, the approved scale, and the bounded route canvas are absent; the headed layout test reports document width 1280 versus a smaller client width.

- [ ] **Step 4: Replace IBM Plex Sans with Inter through npm**

```bash
npm install --save-exact @fontsource/inter@5.2.8
npm uninstall @fontsource/ibm-plex-sans
```

Expected: `package.json` and `package-lock.json` update; IBM Plex Mono remains installed.

Replace the font imports at the top of `frontend/src/main.tsx`:

```tsx
import '@fontsource/ibm-plex-mono/latin-400.css'
import '@fontsource/ibm-plex-mono/latin-700.css'
import '@fontsource/inter/latin-400.css'
import '@fontsource/inter/latin-500.css'
import '@fontsource/inter/latin-700.css'
```

- [ ] **Step 5: Implement approved tokens and global theme**

In `frontend/src/theme/tokens.ts`, set:

```ts
font: {
  ui: '"Inter", sans-serif',
  data: '"IBM Plex Mono", monospace',
  base: 14,
  size: {
    caption: '0.75rem',
    supporting: '0.8125rem',
    body: '0.875rem',
    panelTitle: '0.9375rem',
    sectionTitle: '1.125rem',
    pageTitle: '1.75rem',
  },
  lineHeight: {
    caption: '1rem',
    supporting: '1.125rem',
    body: '1.25rem',
    panelTitle: '1.25rem',
    sectionTitle: '1.5rem',
    pageTitle: '2rem',
  },
},
spacing: { unit: 4 },
size: {
  control: 44,
  sidebar: 264,
  routeCanvas: 1600,
  rule: 1,
  activeRule: 3,
},
```

Remove `desktopMinWidth` from the token object.

In `frontend/src/theme/theme.ts`, retain the existing palette and replace typography with:

Add the Data Grid theme augmentation import beside the existing MUI imports:

```ts
import type {} from '@mui/x-data-grid/themeAugmentation'
```

```ts
typography: {
  fontFamily: tokens.font.ui,
  fontSize: tokens.font.base,
  h1: { fontSize: tokens.font.size.pageTitle, fontWeight: 700, lineHeight: tokens.font.lineHeight.pageTitle },
  h2: { fontSize: tokens.font.size.sectionTitle, fontWeight: 700, lineHeight: tokens.font.lineHeight.sectionTitle },
  h3: { fontSize: tokens.font.size.panelTitle, fontWeight: 700, lineHeight: tokens.font.lineHeight.panelTitle },
  h4: { fontSize: tokens.font.size.panelTitle, fontWeight: 700, lineHeight: tokens.font.lineHeight.panelTitle },
  body1: { fontSize: tokens.font.size.body, lineHeight: tokens.font.lineHeight.body },
  body2: { fontSize: tokens.font.size.supporting, lineHeight: tokens.font.lineHeight.supporting },
  caption: { fontSize: tokens.font.size.caption, lineHeight: tokens.font.lineHeight.caption },
},
```

Remove `body.minWidth`. Set `#root` to `minWidth: 0` and `minHeight: '100vh'`. Set `MuiListSubheader` to `tokens.font.ui`, uppercase, `0.08em` letter spacing, and caption sizing. Add `MuiPaper.outlined` border/no-shadow defaults and MUI Data Grid theme augmentation/header contrast. Do not apply IBM Plex Mono to every Data Grid cell globally.

- [ ] **Step 6: Implement the centered shell canvas**

Replace the current main element in `frontend/src/app/AppShell.tsx` with:

```tsx
<Box
  component="main"
  sx={{
    flexGrow: 1,
    minWidth: 0,
    px: 6,
    py: 6,
    '@media (min-width: 1440px)': { px: 8 },
  }}
>
  <Box sx={{ width: '100%', maxWidth: tokens.size.routeCanvas, minWidth: 0, mx: 'auto' }}>
    <Outlet />
  </Box>
</Box>
```

Set the navigation container to `py: 4`, zero List vertical padding, and `mt: 6` between adjacent groups. Preserve all links, group names, the 264px Drawer, active rail, and `aria-current` behavior.

- [ ] **Step 7: Verify Task 1 green**

```bash
npm test -- src/theme/theme.test.ts src/app/routes.test.tsx
npx playwright test --config playwright.config.ts --project=desktop-1280 --headed tests/e2e/layout.spec.ts
```

Expected: focused Vitest passes; all six headed 1280 layout cases pass without document overflow.

---

### Task 2: Shared Chart, Filter, Dialog, and Technical-State Presentation

**Files:**
- Modify: `frontend/src/theme/echartsTheme.ts`
- Modify: `frontend/src/components/charts/EChart.test.tsx`
- Modify: `frontend/src/components/filters/TemporalFilterBar.tsx`
- Modify: `frontend/src/components/filters/TemporalFilterBar.test.tsx`
- Modify: `frontend/src/components/data/BoundedDataDialog.tsx`
- Modify: `frontend/src/components/data/BoundedDataDialog.test.tsx`
- Modify: `frontend/src/components/states/SensorStatus.tsx`
- Modify: `frontend/src/components/states/states.test.tsx`

**Interfaces:**
- Consumes: Task 1 typography tokens and theme.
- Produces: Inter chart titles/legends, IBM Plex Mono axes/tooltips/technical state values, wrapping temporal filters, and readable bounded-data grids for Tasks 3–8.

- [ ] **Step 1: Add failing shared-presentation assertions**

In `EChart.test.tsx`, assert `buildEChartsTheme(theme)` contains:

```ts
expect(buildEChartsTheme(theme)).toMatchObject({
  textStyle: { fontFamily: tokens.font.ui },
  legend: { textStyle: { fontFamily: tokens.font.ui } },
  tooltip: { textStyle: { fontFamily: tokens.font.data } },
  categoryAxis: { axisLabel: { fontFamily: tokens.font.data } },
  valueAxis: { axisLabel: { fontFamily: tokens.font.data } },
  timeAxis: { axisLabel: { fontFamily: tokens.font.data } },
})
```

In the first TemporalFilterBar test:

```tsx
const filters = screen.getByRole('group', { name: 'Temporal filters' })
expect(filters).toHaveStyle({ width: '100%', minWidth: '0px', flexWrap: 'wrap' })
```

In `states.test.tsx`, render `SensorStatus` with a timestamp and assert its timestamp/age caption computes IBM Plex Mono.

- [ ] **Step 2: Run focused tests and verify red**

```bash
npm test -- src/components/charts/EChart.test.tsx src/components/filters/TemporalFilterBar.test.tsx src/components/data/BoundedDataDialog.test.tsx src/components/states/states.test.tsx
```

Expected: new font-role, wrapping, and technical-state assertions fail.

- [ ] **Step 3: Implement ECharts font roles**

In `frontend/src/theme/echartsTheme.ts`, keep the existing color/theme structure and set:

```ts
textStyle: { color: theme.palette.text.primary, fontFamily: tokens.font.ui },
legend: { textStyle: { color: theme.palette.text.secondary, fontFamily: tokens.font.ui } },
tooltip: {
  backgroundColor: theme.palette.background.paper,
  borderColor: theme.palette.divider,
  textStyle: { color: theme.palette.text.primary, fontFamily: tokens.font.data },
},
categoryAxis: axis,
valueAxis: axis,
timeAxis: axis,
```

Define `axis.axisLabel.fontFamily` and `axis.nameTextStyle.fontFamily` as `tokens.font.data`. Preserve `EChart.tsx` unchanged.

- [ ] **Step 4: Make shared filters wrap without changing their contract**

Change only the opening Stack in `TemporalFilterBar.tsx`:

```tsx
<Stack
  role="group"
  aria-label="Temporal filters"
  direction="row"
  spacing={2}
  useFlexGap
  sx={{
    width: '100%',
    minWidth: 0,
    alignItems: 'center',
    flexWrap: 'wrap',
    rowGap: 1,
    '& > .MuiFormControl-root': { minWidth: 136 },
    '& > .MuiTextField-root': { flex: '1 1 220px', minWidth: 220, maxWidth: 320 },
    '& .MuiInputBase-input, & .MuiNativeSelect-select': {
      fontFamily: tokens.font.data,
      fontVariantNumeric: 'tabular-nums',
    },
  }}
>
```

Retain every prop, label, option, and `onChange` branch.

- [ ] **Step 5: Keep bounded dialog overflow internal**

Apply presentation directly to the existing Data Grid in `BoundedDataDialog.tsx`:

```tsx
columnHeaderHeight={64}
getRowHeight={() => 'auto'}
sx={{
  minWidth: 0,
  '& .MuiDataGrid-cell': {
    fontFamily: tokens.font.data,
    fontVariantNumeric: 'tabular-nums',
    alignItems: 'center',
    lineHeight: 1.3,
    py: 0.5,
    whiteSpace: 'normal',
  },
  '& .MuiDataGrid-columnHeaderTitle': {
    lineHeight: 1.15,
    overflow: 'visible',
    textOverflow: 'clip',
    whiteSpace: 'normal',
  },
}}
```

Do not add new dialog props. Preserve `maxWidth="lg"`, focus behavior, read-only cells, pagination, counts, and callbacks.

- [ ] **Step 6: Style SensorStatus technical values**

Apply this `sx` only to its timestamp/age caption:

```ts
const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const
```

Keep all existing status text and fallback wording.

- [ ] **Step 7: Verify Task 2 green**

```bash
npm test -- src/components/charts/EChart.test.tsx src/components/charts/options.test.ts src/components/filters/TemporalFilterBar.test.tsx src/components/data/BoundedDataDialog.test.tsx src/components/states/states.test.tsx
```

Expected: all scoped component tests pass; EChart resize/update/disposal and dialog keyboard semantics remain unchanged.

---

### Task 3: Overview Route Composition

**Files:**
- Modify: `frontend/src/pages/OverviewPage.tsx`
- Modify: `frontend/src/features/overview/CurrentAlertCard.tsx`
- Modify: `frontend/src/features/overview/SensorMatrix.tsx`
- Modify: `frontend/src/features/overview/ActionQueue.tsx`
- Modify: `frontend/src/pages/OverviewPage.test.tsx`

**Interfaces:**
- Consumes: Task 1 route canvas and Task 2 technical-value styles.
- Produces: one-row four-part summary, wrapped attention actions, and a two-to-three-column bounded sensor matrix.

- [ ] **Step 1: Add a failing technical-value assertion**

Add this local test helper:

```tsx
function expectTechnicalText(element: HTMLElement) {
  expect(getComputedStyle(element).fontFamily).toContain('IBM Plex Mono')
  expect(getComputedStyle(element).fontVariantNumeric).toContain('tabular-nums')
}
```

In the existing populated Overview test, assert the active alert count, score, and threshold use the helper.

- [ ] **Step 2: Run the route test and verify red**

```bash
npm test -- src/pages/OverviewPage.test.tsx
```

Expected: existing behavior assertions pass; new technical-font assertions fail.

- [ ] **Step 3: Implement the Overview hierarchy**

Set the top-level page Stack to `spacing={6}`. Keep the operational summary order and use:

```tsx
gridTemplateColumns: [
  'minmax(0, 1fr)',
  'minmax(0, 1fr)',
  'minmax(0, 1fr)',
  'minmax(180px, 1.25fr)',
].join(' '),
gap: 2,
p: 4,
```

Use this local style for summary values and technical card values:

```ts
const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const
```

In `SensorMatrix.tsx`, replace the fixed three-column grid with:

```ts
gridTemplateColumns: 'repeat(auto-fit, minmax(min(320px, 100%), 1fr))'
```

Set every card to `minWidth: 0` and `p: 4`. Apply `technicalTextSx` to measurement, timestamp, age, score, and threshold values. In `CurrentAlertCard.tsx`, `SensorMatrix.tsx`, and `ActionQueue.tsx`, add `useFlexGap` and `flexWrap: 'wrap'` to link/action rows. Do not change links or lifecycle callbacks.

- [ ] **Step 4: Verify Task 3 green**

```bash
npm test -- src/pages/OverviewPage.test.tsx
```

Expected: the complete Overview behavior suite and new presentation assertions pass.

---

### Task 4: Sensor Detail Route Composition

**Files:**
- Modify: `frontend/src/pages/SensorDetailPage.tsx`
- Modify: `frontend/src/features/sensors/SensorHistoryPanel.tsx`
- Modify: `frontend/src/features/sensors/RelatedAlertHistory.tsx`
- Modify: `frontend/src/pages/SensorDetailPage.test.tsx`

**Interfaces:**
- Consumes: Task 2 wrapping TemporalFilterBar and bounded dialog.
- Produces: readable sensor identity/snapshot, balanced history summaries, full-width chart, and responsive related-event cards.

- [ ] **Step 1: Add failing semantic and technical assertions**

In the existing populated Sensor Detail test, assert the nested selected sensor value and snapshot measurements compute IBM Plex Mono. In the bounded-data test, assert a technical dialog grid cell computes IBM Plex Mono.

- [ ] **Step 2: Run focused tests and verify red**

```bash
npm test -- src/pages/SensorDetailPage.test.tsx src/components/filters/TemporalFilterBar.test.tsx
```

Expected: existing route/filter behavior passes; new technical-value assertions fail.

- [ ] **Step 3: Implement route composition**

Set the page Stack to `spacing={6}`. Wrap the selected sensor value in a `Box component="span"` using `tokens.font.data`. Set snapshot Paper padding to `p: 4`; make temperature/RH rows wrap with `useFlexGap` and apply the technical style.

In `SensorHistoryPanel.tsx`, keep the existing two-column summary grid, chart height 620, option builders, data rows, and dialog trigger. Add `minWidth: 0` and `p: 4` to both summary Papers; style returned counts with IBM Plex Mono.

In `RelatedAlertHistory.tsx`, use:

```ts
gridTemplateColumns: 'repeat(auto-fit, minmax(min(320px, 100%), 1fr))'
```

Set cards to `minWidth: 0`, `p: 4`, and apply IBM Plex Mono plus `overflowWrap: 'anywhere'` to event time, alert ID, actor, and inference-window values.

- [ ] **Step 4: Verify Task 4 green**

```bash
npm test -- src/pages/SensorDetailPage.test.tsx src/components/filters/TemporalFilterBar.test.tsx src/components/data/BoundedDataDialog.test.tsx
```

Expected: route URL behavior, independent errors, gaps, bounded rows, filters, and new visual semantics pass.

---

### Task 5: Alerts Route Composition

**Files:**
- Modify: `frontend/src/pages/AlertsPage.tsx`
- Modify: `frontend/src/features/alerts-ui/AlertsGrid.tsx`
- Modify: `frontend/src/features/alerts-ui/AlertLifecycleActions.tsx`
- Modify: `frontend/src/features/alerts-ui/AlertEventHistory.tsx`
- Modify: `frontend/src/pages/AlertsPage.test.tsx`

**Interfaces:**
- Consumes: Task 1 Data Grid theme and route canvas.
- Produces: wrapping filter surface, readable server-paged grid, wrapped lifecycle actions, and technical immutable-event values.

- [ ] **Step 1: Add failing technical-value assertions**

In the existing populated Alerts test, assert the From input and an alert-ID grid cell compute IBM Plex Mono. Keep lifecycle and pagination tests unchanged.

- [ ] **Step 2: Run focused tests and verify red**

```bash
npm test -- src/pages/AlertsPage.test.tsx src/features/alerts/lifecycle.test.tsx
```

Expected: behavior locks pass; new technical-font assertions fail.

- [ ] **Step 3: Implement the Alerts hierarchy**

Set the page Stack to `spacing={6}` and the filter Paper to `p: 4`. Change its control Stack to `useFlexGap`, `flexWrap: 'wrap'`, and stable 136px select / 220px text-field minimums. Apply IBM Plex Mono to input/select values only.

In `AlertsGrid.tsx`, preserve field names, rendering, selection, pagination, and callbacks. Use:

```ts
const columnWidths = {
  alert_id: { flex: 1.25, minWidth: 150 },
  device_id: { flex: 0.7, minWidth: 80 },
  status: { flex: 0.9, minWidth: 105 },
  latest_event_ts: { flex: 1.5, minWidth: 190 },
  actions: { flex: 1.65, minWidth: 230 },
} as const
```

Set `columnHeaderHeight={64}`. Allow header and cell text to wrap internally, use IBM Plex Mono for technical cells, and keep horizontal overflow inside the Data Grid.

Add wrapping to `AlertLifecycleActions` without changing which actions appear. Apply IBM Plex Mono and safe wrapping to event timestamp, alert ID, sensor ID, and actor in `AlertEventHistory.tsx`.

- [ ] **Step 4: Verify Task 5 green**

```bash
npm test -- src/pages/AlertsPage.test.tsx src/features/alerts/lifecycle.test.tsx
```

Expected: filter scoping, paging, selection, mutation, retry, conflict, and new presentation assertions pass.

---

### Task 6: EDA Route Composition

**Files:**
- Modify: `frontend/src/pages/EdaPage.tsx`
- Modify: `frontend/src/features/eda/EdaFilters.tsx`
- Modify: `frontend/src/features/eda/DistributionPanel.tsx`
- Modify: `frontend/src/features/eda/CoveragePanel.tsx`
- Modify: `frontend/src/features/eda/MissingnessPanel.tsx`
- Modify: `frontend/src/features/eda/TemporalPatternsPanel.tsx`
- Modify: `frontend/src/features/eda/CorrelationPanel.tsx`
- Modify: `frontend/src/features/eda/SensorComparisonPanel.tsx`
- Modify: `frontend/src/features/eda/CandidateOutliersPanel.tsx`
- Modify: `frontend/src/pages/EdaPage.test.tsx`

**Interfaces:**
- Consumes: shared ECharts/dialog/filter presentation.
- Produces: paired quality/missingness, bounded distribution grid, full-width temporal/correlation panels, and preserved five chart alternatives.

- [ ] **Step 1: Add a failing composition test**

Append to `EdaPage.test.tsx`:

```tsx
it('groups the approved EDA composition and preserves all five chart alternatives', async () => {
  renderEda(`/eda?sensor=n5&from=${from}&to=${to}&bucket=5m`)
  const quality = await screen.findByRole('group', { name: 'Quality and missingness' })
  expect(within(quality).getByRole('region', { name: 'Quality and coverage' })).toBeVisible()
  expect(within(quality).getByRole('region', { name: 'Missingness' })).toBeVisible()

  const distributions = await screen.findByRole('group', { name: 'Distribution panels' })
  for (const name of [
    'Temperature distribution',
    'Relative humidity distribution',
    'Anomaly score distribution',
  ]) {
    expect(within(distributions).getByRole('article', { name })).toBeVisible()
  }
  await waitFor(() => expect(screen.getAllByRole('button', { name: 'Lihat data' })).toHaveLength(5))
})
```

- [ ] **Step 2: Run the EDA test and verify red**

```bash
npm test -- src/pages/EdaPage.test.tsx src/components/charts/options.test.ts
```

Expected: the new semantic groups/articles fail; existing query/error/chart contracts pass.

- [ ] **Step 3: Implement the EDA composition**

Set the page Stack to `spacing={6}`. Wrap `CoveragePanel` and `MissingnessPanel` in:

```tsx
<Box
  role="group"
  aria-label="Quality and missingness"
  sx={{
    display: 'grid',
    gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
    gap: 4,
    alignItems: 'stretch',
    '& > *': { minWidth: 0 },
  }}
>
```

Make both EDA filter rows wrap with `useFlexGap`, `flexWrap: 'wrap'`, and `minWidth: 0`; preserve bounds and X/Y rules.

In `DistributionPanel.tsx`, make the heading/control row wrap, then use:

```ts
gridTemplateColumns: 'repeat(auto-fit, minmax(min(320px, 100%), 1fr))'
```

Each distribution Paper becomes `component="article"`, receives its exact accessible distribution name, `p: 4`, `minWidth: 0`, and a full-height Stack. Align each **Lihat data** button with `mt: 'auto'`. Keep all histogram branches/dialogs unchanged.

Use `p: 4`, `minWidth: 0`, and consistent section headings across the remaining EDA panels. Apply IBM Plex Mono only to returned counts, statistical values, correlation values, sensor IDs, numeric table cells, candidate scores, and timestamps. Do not modify option builders, query arguments, or data rows.

- [ ] **Step 4: Verify Task 6 green**

```bash
npm test -- src/pages/EdaPage.test.tsx src/features/eda/queries.test.tsx src/components/charts/options.test.ts src/components/data/BoundedDataDialog.test.tsx
```

Expected: all seven EDA sections, URL/local controls, independent errors, five chart alternatives, and option invariants pass.

---

### Task 7: Model Evaluation Route Composition

**Files:**
- Modify: `frontend/src/pages/ModelEvaluationPage.tsx`
- Modify: `frontend/src/features/modelEvaluation/MetricsPanel.tsx`
- Modify: `frontend/src/features/modelEvaluation/LabeledMetricsPanels.tsx`
- Modify: `frontend/src/pages/ModelEvaluationPage.test.tsx`

**Interfaces:**
- Consumes: Task 2 chart/dialog presentation.
- Produces: compact selector, two-column artifact metadata, scalar metric grid, and three named bounded chart panels.

- [ ] **Step 1: Add a failing semantic composition test**

Add a test that locates:

```tsx
const metadata = await screen.findByRole('region', { name: 'Artifact identity and metadata' })
expect(within(metadata).getByText('Selected version:')).toBeVisible()
expect(within(metadata).getByText('model-v2')).toBeVisible()

const scalarMetrics = screen.getByRole('list', { name: 'Scalar metrics' })
expect(within(scalarMetrics).getAllByRole('listitem')).toHaveLength(2)

const charts = screen.getByRole('group', { name: 'Labeled evaluation charts' })
for (const name of ['Confusion matrix', 'ROC curve', 'Precision recall curve']) {
  const panel = within(charts).getByRole('article', { name })
  expect(within(panel).getByRole('heading', { level: 3, name })).toBeVisible()
  expect(within(panel).getByRole('img', { name })).toBeVisible()
}
```

- [ ] **Step 2: Run the Model Evaluation test and verify red**

```bash
npm test -- src/pages/ModelEvaluationPage.test.tsx src/components/charts/options.test.ts src/components/data/BoundedDataDialog.test.tsx
```

Expected: metadata/list/article semantics fail; existing version normalization, metric gates, chart labels, and dialogs pass.

- [ ] **Step 3: Implement artifact metadata and scalar metrics**

Set page Stack spacing to `6` and cap the existing selector wrapper at 280px. Render metadata in an outlined Paper with `p: 4`, `maxWidth: '84ch'`, an `h2`, and a `dl` grid:

```ts
gridTemplateColumns: 'repeat(2, minmax(0, 1fr))'
```

Render labels as `dt` captions and values as `dd` body text using IBM Plex Mono, zero margin, `minWidth: 0`, and `overflowWrap: 'anywhere'`.

Update existing metadata tests that match a combined label/value string so they scope the metadata region and assert the `dt` label and `dd` value separately. Do not remove any metadata-value assertion.

In `MetricsPanel.tsx`, preserve the declaration-and-presence filter. Render visible values as a named list using:

```ts
gridTemplateColumns: 'repeat(auto-fit, minmax(min(160px, 100%), 1fr))'
```

Each list item uses IBM Plex Mono, `p: 4`, and safe wrapping.

- [ ] **Step 4: Implement named chart panels**

Keep the three existing explicit gates, option builders, ARIA labels, dialog rows/titles, and callbacks. Wrap the visible panels in:

```tsx
<Box
  role="group"
  aria-label="Labeled evaluation charts"
  sx={{
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(min(420px, 100%), 1fr))',
    gap: 4,
    alignItems: 'stretch',
  }}
>
```

Each chart Paper becomes an `article` with its exact chart name, `p: 4`, `minWidth: 0`, and an `h3`. Align its existing **Lihat data** button with `mt: 'auto'`. Do not abstract the three panels or change accessible button names.

- [ ] **Step 5: Verify Task 7 green**

```bash
npm test -- src/pages/ModelEvaluationPage.test.tsx src/features/modelEvaluation/queries.test.tsx src/components/charts/options.test.ts src/components/data/BoundedDataDialog.test.tsx
```

Expected: versions, metadata, declared scalars, chart gates, all three data dialogs, and new semantic composition pass.

---

### Task 8: System Health Route Composition

**Files:**
- Modify: `frontend/src/pages/SystemHealthPage.tsx`
- Modify: `frontend/src/features/systemHealth/StatusSnapshot.tsx`
- Modify: `frontend/src/features/systemHealth/ServiceStatusTable.tsx`
- Modify: `frontend/src/pages/SystemHealthPage.test.tsx`

**Interfaces:**
- Consumes: Task 1 typography and route canvas.
- Produces: readable-width explanation, named two-column freshness snapshot, and internally scroll-contained service table.

- [ ] **Step 1: Add a failing semantic composition test**

Append a test that locates `Latest known system snapshot`, then:

```tsx
const freshness = within(snapshot).getByRole('group', { name: 'Freshness snapshot' })
const poll = within(freshness).getByRole('region', { name: 'Status-poll freshness' })
const telemetry = within(freshness).getByRole('region', { name: 'Telemetry freshness' })
expect(poll).toHaveTextContent('Status poll age: 0 seconds')
expect(telemetry).toHaveTextContent('Telemetry age: 20 seconds')
expect(screen.getByRole('table', { name: 'Service liveness and readiness' })).toBeVisible()
```

- [ ] **Step 2: Run the System Health test and verify red**

```bash
npm test -- src/pages/SystemHealthPage.test.tsx src/features/systemHealth/query.test.tsx
```

Expected: named freshness regions fail; current stale-data and freshness behavior assertions pass.

- [ ] **Step 3: Implement the System Health hierarchy**

Set the page Stack to `spacing={6}` and cap the existing explanatory Typography at `maxWidth: '68ch'`.

Keep the existing two-column snapshot grid, but add `role="group"`, `aria-label="Freshness snapshot"`, and named `section` children for status-poll and telemetry freshness. Apply IBM Plex Mono plus safe wrapping only to checked/displayed/latest timestamps, ages, and sensor counts. Keep all explanatory text and the distinction between reachability, readiness, poll freshness, and telemetry freshness.

Update existing full-line freshness selectors to use `toHaveTextContent` on the named poll/telemetry regions so nested technical-value spans do not weaken the assertions.

In `ServiceStatusTable.tsx`, wrap the existing table in:

```tsx
<TableContainer sx={{ overflowX: 'auto' }}>
```

Set the table to `width: '100%'`, `minWidth: 720`, and `tableLayout: 'fixed'`. Keep its caption and status words. Apply IBM Plex Mono plus safe wrapping to service name and checked-at cells; allow detail text to wrap. Do not add aggregate health or replacement chips.

- [ ] **Step 4: Verify Task 8 green**

```bash
npm test -- src/pages/SystemHealthPage.test.tsx src/features/systemHealth/query.test.tsx
```

Expected: initial error, retained stale data, recovery, distinct freshness facts, named regions, and service table pass.

---

### Task 9: Integrated Layout, Visual, Production, Docker, and Review Gate

**Files:**
- Modify: `frontend/tests/e2e/layout.spec.ts`
- Update intentionally: six existing PNGs under `frontend/tests/e2e/visual.spec.ts-snapshots/`
- Verify only: `frontend/tests/e2e/visual.spec.ts`
- Verify only: behavior and keyboard E2E specs
- Verify only: production/Docker/Nginx assets

**Interfaces:**
- Consumes: completed Tasks 1–8.
- Produces: approved six-route visual evidence and the final all-lanes-pass result.

- [ ] **Step 1: Add route-specific assertions inside the existing six layout cases**

Do not add Playwright cases. Inside the current route loop, branch on the existing route name and assert:

- Overview: navigation width 264px, main left edge 264px, four summary values visible, sensor card text in bounds.
- Sensor Detail: filters/history/related-event text in bounds; open the existing **Lihat data** dialog and verify headers/cells remain within the dialog viewport.
- Alerts: filters, five grid headers, technical cells, actions, pagination, and immutable history are visible.
- EDA: three distribution articles exist; column count is two at 1280 and three at wider targets.
- Model Evaluation: three labeled chart articles exist; column count is two at 1280/1440 and three at 1920; hash uses IBM Plex Mono.
- System Health: freshness sections share the same vertical start and the service table remains visible.

Use bounding boxes and computed fonts; do not add screenshot assertions. Correct the navigation-group font assertion to expect Inter, not IBM Plex Mono.

- [ ] **Step 2: Run the complete generic and route-specific layout matrix**

```bash
npx playwright test --config playwright.config.ts tests/e2e/layout.spec.ts
npx playwright test --config playwright.config.ts --project=desktop-1280 --headed tests/e2e/layout.spec.ts
```

Expected: six cases pass at each configured 1280, 1440, and 1920 project; the headed 1280 rerun confirms vertical-scroll allocation without document overflow.

- [ ] **Step 3: Run scoped behavior and keyboard E2E tests**

```bash
npx playwright test --config playwright.config.ts --project=desktop-1440 tests/e2e/overview.spec.ts tests/e2e/sensor-detail.spec.ts tests/e2e/alerts.spec.ts tests/e2e/analysis.spec.ts tests/e2e/system-health.spec.ts tests/e2e/keyboard.spec.ts
```

Expected: navigation, filters, grid selection, lifecycle actions, retry/conflict behavior, chart dialogs, Escape/Close, and focus restoration pass.

- [ ] **Step 4: Update exactly six visual baselines**

Run serially after `document.fonts.ready` and ECharts rendering waits already present in the visual spec:

```bash
npx playwright test --config playwright.config.ts --project=desktop-1440 tests/e2e/visual.spec.ts --update-snapshots --workers=1
npx playwright test --config playwright.config.ts --project=desktop-1440 tests/e2e/visual.spec.ts --workers=1
```

Expected: exactly six existing PNGs update and the immediate comparison passes. Review every delta for hierarchy, clipping, text retention, sidebar consistency, and chart/table integrity.

- [ ] **Step 5: Run source diagnostics and complete automated acceptance**

Run `lsp_diagnostics` in parallel on every changed TS/TSX file, then:

```bash
npm run lint
npm test
npm run build
npm run test:production
npm run test:e2e
```

Expected: diagnostics contain no new errors; lint exits 0; Vitest reports 226 passing tests (the 219-test baseline plus seven deliberate cases in this plan); build exits 0; production verifier passes one Node test; Playwright preserves the 34-test count because layout cases were enriched rather than multiplied.

- [ ] **Step 6: Verify the production image and SPA runtime**

```bash
docker build --tag anomaly-frontend:verify .
docker run --detach --rm --name anomaly-frontend-verify --publish 8080:80 anomaly-frontend:verify
curl --fail --silent --show-error --output /dev/null http://127.0.0.1:8080/
curl --fail --silent --show-error --output /dev/null http://127.0.0.1:8080/model-evaluation
docker inspect --format '{{.State.Health.Status}}' anomaly-frontend-verify
docker exec anomaly-frontend-verify nginx -t
docker stop anomaly-frontend-verify
```

Expected: image builds, root and deep SPA route return success, health reports `healthy`, Nginx syntax passes, and the container stops cleanly. Do not test `/api/`, `/health`, or `/ready` proxies without a reachable Docker-network host named `api` at port 8000.

- [ ] **Step 7: Run post-implementation visual and five-lane review**

Use the required `visual-qa` workflow for 1280, 1440, and 1920 evidence. Then use `review-work` to run goal/constraint, code quality, security, hands-on QA, and context-mining lanes. Resolve only issues caused by this plan and rerun failed gates.

Expected: visual QA passes and all five final review lanes pass, including the previously failing headed-1280 overflow check.

## Execution Handoff

Execute from `frontend/` unless a step explicitly uses a workspace-relative documentation path. Use Task 1, then Task 2, then Tasks 3–8 in parallel with exclusive ownership, followed by Task 9 sequentially. No Git operations are part of execution.

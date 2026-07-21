# Frontend-First SPA Implementation Plan

> **For execution:** Resume at Task 8. Keep the approved product requirements, but use the three-wave minimal workflow below without another design cycle or per-task review stack.

**Goal:** Build a complete desktop React SPA against deterministic MSW contracts, including six pages, production Nginx serving, and frontend-only acceptance evidence.

**Architecture:** Page components consume feature hooks. Feature hooks own TanStack Query keys, polling, mutations, and URL-derived parameters. Typed adapters own relative requests, timeout handling, Problem Details, and Zod response validation. MSW serves the same contracts only in development and tests.

**Tech Stack:** React, Vite, TypeScript, MUI Core, MUI X Data Grid Community, Apache ECharts, React Router, TanStack Query, Zod, MSW, Vitest, React Testing Library, Playwright, Docker, Nginx.

**Global Constraints:** This plan creates only `frontend/`. Backend, MQTT, TimescaleDB, PyTorch, Docker Compose, authentication, SSR, Redux, MUI X Charts, MUI X Pro, Recharts, Nivo, CSV upload, mobile layouts, and a standalone mock API remain excluded. Use the approved action-first mockup only as visual reference. The approved written spec overrides mockup sample data.

---

## Fixed contract decisions

### Product limits and routes

| Item | Fixed value |
|---|---|
| Sensors | `n1`, `n2`, `n3`, `n4`, `n5`, `n6` only |
| Routes | `/`, `/sensors/:sensorId`, `/alerts`, `/eda`, `/model-evaluation`, `/system-health` only |
| Canonical URL keys | `sensor`, `from`, `to`, `bucket`, `model_version` |
| Browser-only scenario key | `__scenario`, development only, never treated as product state |
| Buckets | `raw`, `1m`, `5m`, `15m`, `1h`, `1d` |
| API timeout | 8,000 ms |
| Latest telemetry and current-alert polling | 10,000 ms |
| System-status polling | 30,000 ms |
| History, inference, EDA, evaluation polling | None. Fetch only when normalized parameters change. |
| Desktop behavior checks | Chromium at `1280x900`, `1440x900`, `1920x900` |
| Visual baselines | Exactly 6 at `1440x900`, one per route. The 1280 and 1920 projects use DOM overflow/clipping assertions, not screenshot baselines. No mobile project. |

### Transport and lifecycle

Pages never call `fetch`. The sole transport path is:

```text
Page -> feature hook -> typed adapter -> relative request -> MSW in development/test, FastAPI later
```

Application requests use `/api/...`. API liveness and readiness use exact root paths `/health` and `/ready`. The production build has no MSW initialization, worker, handlers, fixtures, or scenario data in its runtime path. The one valid alert lifecycle is `detected -> acknowledged -> resolved`; UI text calls `detected` **active**. Mutations are pessimistic. One lifecycle action creates one body and every retry sends the identical `command_id`, `event_ts`, and optional `note`.

### Endpoint ledger

| Adapter export | Method and path | Bound or special rule |
|---|---|---|
| `getLatestTelemetry` | `GET /api/telemetry/latest` | optional `device_id`; polls every 10 seconds |
| `getTelemetryHistory` | `GET /api/telemetry/history` | required device/time; raw at most 5,000, bucketed at most 2,000 |
| `getInferenceResults` | `GET /api/inference-results` | required device/time; same point limits as history |
| `getAlertEvents` | `GET /api/alert-events` | at most 200 immutable rows |
| `getCurrentAlerts` | `GET /api/alerts/current` | page size 1 through 100; no time parameters |
| `acknowledgeAlert` | `POST /api/alerts/:alertId/acknowledge` | accepts caller-supplied body unchanged |
| `resolveAlert` | `POST /api/alerts/:alertId/resolve` | active alert returns 409 Problem Details |
| `getEdaSummary` | `GET /api/eda/summary` | temporal panel data stays on history/inference endpoints |
| `getEdaDistributions` | `GET /api/eda/distributions` | `bins` is 5 through 100 |
| `getEdaCorrelation` | `GET /api/eda/correlation` | `max_points` is 100 through 5,000; fields differ |
| `getModelEvaluations` | `GET /api/model-evaluations` | page size 1 through 50 |
| `getModelEvaluation` | `GET /api/model-evaluations/:version` | only declared artifact metrics render |
| `getSystemStatus` | `GET /api/system/status` | polls every 30 seconds |
| `getLiveness` | `GET /health` | root-path exception, no page polling requirement |
| `getReadiness` | `GET /ready` | root-path exception, no page polling requirement |

### Exact greenfield file map

Only create the following frontend tree while executing this plan. Tests live beside their unit unless the path below says otherwise.

```text
frontend/
  .dockerignore
  .gitignore
  Dockerfile
  nginx.conf
  package.json
  package-lock.json
  index.html
  eslint.config.js
  tsconfig.json
  tsconfig.app.json
  tsconfig.node.json
  vite.config.ts
  playwright.config.ts
  public-dev/
    mockServiceWorker.js
  src/
    vite-env.d.ts
    main.tsx
    app/
      App.tsx
      AppProviders.tsx
      AppShell.tsx
      navigation.ts
      queryClient.ts
      router.tsx
      routes.test.tsx
    pages/
      OverviewPage.tsx
      OverviewPage.test.tsx
      SensorDetailPage.tsx
      SensorDetailPage.test.tsx
      AlertsPage.tsx
      AlertsPage.test.tsx
      EdaPage.tsx
      EdaPage.test.tsx
      ModelEvaluationPage.tsx
      ModelEvaluationPage.test.tsx
      SystemHealthPage.tsx
      SystemHealthPage.test.tsx
    features/
      filters/urlFilters.ts
      filters/urlFilters.test.ts
      telemetry/queries.ts
      telemetry/queries.test.tsx
      inference/queries.ts
      inference/queries.test.tsx
      alerts/queries.ts
      alerts/alertCommand.ts
      alerts/useAlertLifecycleMutation.ts
      alerts/lifecycle.test.tsx
      overview/useOverviewData.ts
      overview/ActionQueue.tsx
      overview/CurrentAlertCard.tsx
      overview/SensorMatrix.tsx
      sensors/SensorHistoryPanel.tsx
      sensors/RelatedAlertHistory.tsx
      alerts-ui/AlertsGrid.tsx
      alerts-ui/AlertEventHistory.tsx
      alerts-ui/AlertLifecycleActions.tsx
      eda/queries.ts
      eda/queries.test.tsx
      eda/EdaFilters.tsx
      eda/CoveragePanel.tsx
      eda/MissingnessPanel.tsx
      eda/DistributionPanel.tsx
      eda/TemporalPatternsPanel.tsx
      eda/CorrelationPanel.tsx
      eda/SensorComparisonPanel.tsx
      eda/CandidateOutliersPanel.tsx
      modelEvaluation/queries.ts
      modelEvaluation/queries.test.tsx
      modelEvaluation/VersionSelect.tsx
      modelEvaluation/MetricsPanel.tsx
      modelEvaluation/LabeledMetricsPanels.tsx
      systemHealth/query.ts
      systemHealth/query.test.tsx
      systemHealth/StatusSnapshot.tsx
      systemHealth/ServiceStatusTable.tsx
    components/
      states/PanelSkeleton.tsx
      states/EmptyState.tsx
      states/ApiErrorPanel.tsx
      states/PollingFailureNotice.tsx
      states/SensorStatus.tsx
      states/states.test.tsx
      filters/TemporalFilterBar.tsx
      filters/TemporalFilterBar.test.tsx
      data/BoundedDataDialog.tsx
      data/BoundedDataDialog.test.tsx
      charts/EChart.tsx
      charts/EChart.test.tsx
      charts/temporalOptions.ts
      charts/edaOptions.ts
      charts/evaluationOptions.ts
      charts/options.test.ts
    api/
      errors.ts
      http.ts
      telemetry.ts
      inference.ts
      alerts.ts
      eda.ts
      modelEvaluations.ts
      systemHealth.ts
      api.test.ts
    contracts/
      common.ts
      telemetry.ts
      inference.ts
      alerts.ts
      eda.ts
      modelEvaluation.ts
      systemHealth.ts
      contracts.test.ts
    mocks/
      scenario.ts
      state.ts
      handlers.ts
      browser.ts
      node.ts
      handlers.test.ts
      fixtures/telemetry.ts
      fixtures/inference.ts
      fixtures/alerts.ts
      fixtures/eda.ts
      fixtures/modelEvaluations.ts
      fixtures/systemHealth.ts
    theme/
      tokens.ts
      theme.ts
      echartsTheme.ts
    test/
      setup.ts
      renderApp.tsx
  tests/
    e2e/
      helpers.ts
      overview.spec.ts
      sensor-detail.spec.ts
      alerts.spec.ts
      analysis.spec.ts
      system-health.spec.ts
      keyboard.spec.ts
      visual.spec.ts
      visual.spec.ts-snapshots/
    production/
      verify-dist.test.mjs
```

## Dependency graph and parallel waves

Tasks 1–7 are the completed prerequisite baseline. Execute the remaining work in exactly three waves:

| Task | Depends on | Exclusive ownership | Blocks |
|---|---|---|---|
| 8. Sensor Detail and History | Completed Tasks 3, 4, 5, 6 | `SensorDetailPage*`, `features/sensors/**` | 13, 14 |
| 9. Alerts | Completed Tasks 3, 4, 5 | `AlertsPage*`, `features/alerts-ui/**` | 13, 14 |
| 10. EDA | Completed Tasks 3, 4, 5, 6 | `EdaPage*`, `features/eda/**` | 13, 14 |
| 11. Model Evaluation | Completed Tasks 3, 4, 5, 6 | `ModelEvaluationPage*`, `features/modelEvaluation/**` | 13, 14 |
| 12. System Health | Completed Tasks 3, 4, 5 | `SystemHealthPage*`, `features/systemHealth/**` | 13, 14 |
| 13. Playwright and visuals | Tasks 8–12 | `playwright.config.ts`, `tests/e2e/**` | 15 |
| 14. Production Docker and Nginx | Tasks 8–12 and completed Task 3 | `Dockerfile`, `nginx.conf`, `.dockerignore`, `tests/production/**` | 15 |
| 15. Acceptance gate | Tasks 13, 14 | No new files | None |

```text
Wave 1: Tasks 8, 9, 10, 11, and 12 in parallel
Wave 2: Tasks 13 and 14 in parallel after Wave 1 passes
Wave 3: Task 15 sequentially after Tasks 13 and 14 pass
```

For Tasks 8–12, run only the task's existing targeted red/green Vitest commands and diagnostics on every changed TS/TSX file. Do not run an unscoped full suite, build, Playwright, browser visual QA, Oracle, Review Work, pixel diff, or create report artifacts per task. Shared prerequisite files are read-only. Task 13 owns browser, keyboard, resize, and visual evidence. Task 15 owns the full suite, complete acceptance commands, and one final review.

## Task 1: Foundation

**Depends on:** None. **Produces:** the Vite application, desktop shell, providers, theme, exactly six routable title-only page modules, test harness, and baseline scripts.

**Files:** Create `frontend/package.json`, `frontend/index.html`, `frontend/eslint.config.js`, `frontend/tsconfig.json`, `frontend/tsconfig.app.json`, `frontend/tsconfig.node.json`, `frontend/vite.config.ts`, `frontend/src/vite-env.d.ts`, `frontend/src/main.tsx`, `frontend/src/app/App.tsx`, `frontend/src/app/AppProviders.tsx`, `frontend/src/app/AppShell.tsx`, `frontend/src/app/navigation.ts`, `frontend/src/app/queryClient.ts`, `frontend/src/app/router.tsx`, `frontend/src/app/routes.test.tsx`, `frontend/src/theme/tokens.ts`, `frontend/src/theme/theme.ts`, `frontend/src/theme/echartsTheme.ts`, `frontend/src/test/setup.ts`, `frontend/src/test/renderApp.tsx`, and `frontend/src/pages/{OverviewPage,SensorDetailPage,AlertsPage,EdaPage,ModelEvaluationPage,SystemHealthPage}.tsx`.

**Interfaces:**

```ts
// frontend/src/app/navigation.ts
export interface NavigationItem {
  path: '/' | '/sensors/n1' | '/alerts' | '/eda' | '/model-evaluation' | '/system-health'
  label: string
  group: 'operations' | 'analysis' | 'system'
}

export const navigationItems: readonly NavigationItem[] = [
  { path: '/', label: 'Overview', group: 'operations' },
  { path: '/sensors/n1', label: 'Sensors', group: 'operations' },
  { path: '/alerts', label: 'Alerts', group: 'operations' },
  { path: '/eda', label: 'EDA', group: 'analysis' },
  { path: '/model-evaluation', label: 'Model Evaluation', group: 'analysis' },
  { path: '/system-health', label: 'System Health', group: 'system' },
]
```

**Consumes:** no earlier code. **Produces:** `createAppRouter(initialEntries?: string[]): Router`, `AppProviders`, `AppShell`, `navigationItems`, six route modules, and `renderApp(route: string): RenderResult`.

- [ ] Confirm Node is acceptable with `node --version`; expect `v20.19.0` or later, or `v22.12.0` or later.
- [ ] Create the greenfield base with `npm create vite@latest frontend -- --template react-ts`.
- [ ] From `frontend/`, install exact runtime packages: `npm install --save-exact @emotion/react @emotion/styled @fontsource/ibm-plex-mono @fontsource/ibm-plex-sans @mui/material @mui/x-data-grid @tanstack/react-query echarts react-router-dom zod`.
- [ ] From `frontend/`, install exact developer packages: `npm install --save-dev --save-exact @playwright/test @testing-library/jest-dom @testing-library/react @testing-library/user-event jsdom msw vitest`.
- [ ] Create the red route test before shell code. Run `npm test -- src/app/routes.test.tsx`; expect an import failure for `./router` and `./navigation`.

```tsx
// frontend/src/app/routes.test.tsx
import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import { navigationItems } from './navigation'
import { renderApp } from '../test/renderApp'

const routes = [
  ['/', 'Overview'],
  ['/sensors/n4', 'Sensor Detail & History'],
  ['/alerts', 'Alerts'],
  ['/eda', 'EDA'],
  ['/model-evaluation', 'Model Evaluation'],
  ['/system-health', 'System Health'],
] as const

describe('application routes', () => {
  it.each(routes)('renders %s as %s', (path, heading) => {
    renderApp(path)
    expect(screen.getByRole('heading', { name: heading })).toBeVisible()
  })

  it('redirects an unknown path to Overview', () => {
    renderApp('/not-a-route')
    expect(screen.getByRole('heading', { name: 'Overview' })).toBeVisible()
  })

  it('renders all six approved sidebar entries in their fixed desktop groups', () => {
    renderApp('/')
    expect(navigationItems).toHaveLength(6)
    const navigation = screen.getByRole('navigation', { name: 'Primary navigation' })
    expect(within(navigation).getByRole('link', { name: 'Overview' })).toHaveAttribute('href', '/')
    expect(within(navigation).getByRole('link', { name: 'Sensors' })).toHaveAttribute('href', '/sensors/n1')
    expect(within(navigation).getByRole('link', { name: 'Alerts' })).toHaveAttribute('href', '/alerts')
    expect(within(navigation).getByText('Operations')).toBeVisible()
    expect(within(navigation).getByText('Analysis')).toBeVisible()
    expect(within(navigation).getByText('System')).toBeVisible()
  })
})
```

- [ ] Create the shell, router, providers, theme, and six named title-only route modules with the following bounded surface. This snippet defines every import it uses from this task.

```tsx
// frontend/src/app/router.tsx
import { Navigate, createBrowserRouter, createMemoryRouter } from 'react-router-dom'
import { AppShell } from './AppShell'
import { OverviewPage } from '../pages/OverviewPage'
import { SensorDetailPage } from '../pages/SensorDetailPage'
import { AlertsPage } from '../pages/AlertsPage'
import { EdaPage } from '../pages/EdaPage'
import { ModelEvaluationPage } from '../pages/ModelEvaluationPage'
import { SystemHealthPage } from '../pages/SystemHealthPage'

const routes = [{ element: <AppShell />, children: [
    { path: '/', element: <OverviewPage /> },
    { path: '/sensors/:sensorId', element: <SensorDetailPage /> },
    { path: '/alerts', element: <AlertsPage /> },
    { path: '/eda', element: <EdaPage /> },
    { path: '/model-evaluation', element: <ModelEvaluationPage /> },
    { path: '/system-health', element: <SystemHealthPage /> },
    { path: '*', element: <Navigate to="/" replace /> },
  ]}]

export function createAppRouter(initialEntries?: string[]) {
  return initialEntries ? createMemoryRouter(routes, { initialEntries }) : createBrowserRouter(routes)
}

// frontend/src/app/App.tsx
import { RouterProvider } from 'react-router-dom'
import { AppProviders } from './AppProviders'
import { createAppRouter } from './router'
export function App() { return <AppProviders><RouterProvider router={createAppRouter()} /></AppProviders> }

// frontend/src/app/AppShell.tsx
import { Box, Drawer, List, ListItemButton, ListItemText, ListSubheader } from '@mui/material'
import { NavLink, Outlet } from 'react-router-dom'
import { navigationItems, type NavigationItem } from './navigation'

const desktopSidebarWidth = 264
const groups: readonly { label: 'Operations' | 'Analysis' | 'System'; value: NavigationItem['group'] }[] = [
  { label: 'Operations', value: 'operations' },
  { label: 'Analysis', value: 'analysis' },
  { label: 'System', value: 'system' },
]

export function AppShell() {
  return <Box sx={{ display: 'flex', minHeight: '100vh' }}><Drawer variant="permanent" sx={{ width: desktopSidebarWidth, flexShrink: 0, '& .MuiDrawer-paper': { boxSizing: 'border-box', width: desktopSidebarWidth } }}><Box component="nav" aria-label="Primary navigation" sx={{ pt: 2 }}>{groups.map(group => <List key={group.value} subheader={<ListSubheader>{group.label}</ListSubheader>}>{navigationItems.filter(item => item.group === group.value).map(item => <ListItemButton key={item.path} component={NavLink} to={item.path}><ListItemText primary={item.label} /></ListItemButton>)}</List>)}</Box></Drawer><Box component="main" sx={{ flexGrow: 1, minWidth: 0, p: 3 }}><Outlet /></Box></Box>
}

// frontend/src/pages/OverviewPage.tsx
export function OverviewPage() { return <h1>Overview</h1> }
// frontend/src/pages/SensorDetailPage.tsx
export function SensorDetailPage() { return <h1>Sensor Detail & History</h1> }
// frontend/src/pages/AlertsPage.tsx
export function AlertsPage() { return <h1>Alerts</h1> }
// frontend/src/pages/EdaPage.tsx
export function EdaPage() { return <h1>EDA</h1> }
// frontend/src/pages/ModelEvaluationPage.tsx
export function ModelEvaluationPage() { return <h1>Model Evaluation</h1> }
// frontend/src/pages/SystemHealthPage.tsx
export function SystemHealthPage() { return <h1>System Health</h1> }
```

```tsx
// frontend/src/test/renderApp.tsx
import { render, type RenderResult } from '@testing-library/react'
import { RouterProvider } from 'react-router-dom'
import { AppProviders } from '../app/AppProviders'
import { createAppRouter } from '../app/router'

export function renderApp(route: string): RenderResult {
  return render(<AppProviders><RouterProvider router={createAppRouter([route])} /></AppProviders>)
}
```

- [ ] Set scripts to `"lint": "eslint ."`, `"test": "vitest run"`, `"test:watch": "vitest"`, `"test:e2e": "playwright test"`, and `"test:production": "node --test tests/production/verify-dist.test.mjs"`. Configure Vitest through `vite.config.ts` with `environment: 'jsdom'` and `setupFiles: ['./src/test/setup.ts']`.
- [ ] Run `npm test -- src/app/routes.test.tsx`; expect all route tests to pass.
- [ ] Run `npm run lint && npm run build`; expect both commands to exit 0 and `frontend/dist/` to exist.

**Acceptance:** exactly six routes render in one desktop shell; the fixed desktop sidebar exposes exactly six links grouped as Operations (Overview, Sensors, Alerts), Analysis (EDA, Model Evaluation), and System (System Health); `Sensors` links to `/sensors/n1`; the route template remains `/sensors/:sensorId`; unknown routes redirect to `/`; no mobile navigation, Redux, backend host environment variable, MUI X Charts, or additional page appears.

## Task 2: Contracts and adapters

**Depends on:** Task 1. **Consumes:** the TypeScript/Vitest foundation. **Produces:** strict Zod runtime schemas, typed contracts, `ApiError`, the only `fetch` call site, and all endpoint adapters.

**Files:** Create `frontend/src/contracts/common.ts`, `telemetry.ts`, `inference.ts`, `alerts.ts`, `eda.ts`, `modelEvaluation.ts`, `systemHealth.ts`, `contracts.test.ts`, `frontend/src/api/errors.ts`, `http.ts`, `telemetry.ts`, `inference.ts`, `alerts.ts`, `eda.ts`, `modelEvaluations.ts`, `systemHealth.ts`, and `api.test.ts`.

**Interfaces:**

```ts
// frontend/src/contracts/common.ts
import { z } from 'zod'

export const sensorIds = ['n1', 'n2', 'n3', 'n4', 'n5', 'n6'] as const
export const SensorIdSchema = z.enum(sensorIds)
export type SensorId = z.infer<typeof SensorIdSchema>
export const BucketSchema = z.enum(['raw', '1m', '5m', '15m', '1h', '1d'])
export type Bucket = z.infer<typeof BucketSchema>
export const FreshnessSchema = z.enum(['fresh', 'stale', 'unknown'])
export type Freshness = z.infer<typeof FreshnessSchema>
export const AvailabilitySchema = z.enum(['online', 'offline', 'unknown'])
export type Availability = z.infer<typeof AvailabilitySchema>
export const AlertStatusSchema = z.enum(['detected', 'acknowledged', 'resolved'])
export type AlertStatus = z.infer<typeof AlertStatusSchema>
export const Rfc3339Schema = z.string().datetime({ offset: true })
export const ProblemDetailsSchema = z.object({
  type: z.string().url(), title: z.string(), status: z.number().int(),
  detail: z.string(), instance: z.string(), request_id: z.string(),
  errors: z.record(z.string(), z.array(z.string())).optional(),
})
export type ProblemDetails = z.infer<typeof ProblemDetailsSchema>

export interface AlertCommandRequest { command_id: string; event_ts: string; note?: string }
export type ApiPath = `/api/${string}` | '/health' | '/ready'
```

```ts
// frontend/src/api/errors.ts and frontend/src/api/http.ts
import type { ZodType } from 'zod'
import { ProblemDetailsSchema, type ProblemDetails, type ApiPath } from '../contracts/common'

export type ApiErrorKind = 'problem' | 'schema' | 'network' | 'timeout'
export class ApiError extends Error {
  constructor(public readonly kind: ApiErrorKind, message: string, public readonly status?: number,
    public readonly requestId?: string, public readonly problem?: ProblemDetails) { super(message) }
}

export async function requestJson<T>(path: ApiPath, schema: ZodType<T>, options: Omit<RequestInit, 'signal'> & { signal?: AbortSignal; timeoutMs?: number } = {}): Promise<T> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort('timeout'), options.timeoutMs ?? 8_000)
  const signal = options.signal ? AbortSignal.any([options.signal, controller.signal]) : controller.signal
  try {
    const response = await fetch(path, { ...options, signal, headers: { accept: 'application/json', ...options.headers } })
    const body: unknown = await response.json().catch(() => undefined)
    if (!response.ok) {
      const problem = ProblemDetailsSchema.safeParse(body)
      throw new ApiError('problem', problem.success ? problem.data.detail : `HTTP ${response.status}`, response.status, problem.success ? problem.data.request_id : undefined, problem.success ? problem.data : undefined)
    }
    const parsed = schema.safeParse(body)
    if (!parsed.success) throw new ApiError('schema', parsed.error.message, undefined, typeof body === 'object' && body !== null && 'request_id' in body && typeof body.request_id === 'string' ? body.request_id : undefined)
    return parsed.data
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (controller.signal.aborted) throw new ApiError('timeout', 'Request timed out after 8000 ms')
    throw new ApiError('network', error instanceof Error ? error.message : 'Network request failed')
  } finally { window.clearTimeout(timeout) }
}
```

Every endpoint module exports the exact adapter names in the endpoint ledger. `telemetry.ts`, `inference.ts`, `alerts.ts`, `eda.ts`, `modelEvaluations.ts`, and `systemHealth.ts` construct `URLSearchParams`, reject invalid caller input by schema before transport, call `requestJson`, and return the matching response type.

- [ ] Create red tests that parse one valid response for every endpoint and reject an unknown sensor, an offset-free timestamp, a reversed range, out-of-range bounds, invalid alert action flags, undeclared metric keys, and labeled-only structures on an unlabeled artifact.
- [ ] Create API tests for relative URL construction, query encoding, caller cancellation, the 8-second timeout, Problem Details retention, non-JSON failure handling, and invalid success payloads with a raw `request_id`.
- [ ] Run `npm test -- src/contracts/contracts.test.ts src/api/api.test.ts`; expect module-not-found failures for contracts and adapters.

```ts
// frontend/src/api/api.test.ts
import { describe, expect, it, vi } from 'vitest'
import { requestJson } from './http'
import { z } from 'zod'

describe('requestJson', () => {
  it('rejects malformed success data as a schema error with its request id', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ request_id: 'req_schema', sensors: 'wrong' }), { status: 200 })))
    await expect(requestJson('/api/telemetry/latest', z.object({ request_id: z.string(), sensors: z.array(z.unknown()) }))).rejects.toMatchObject({ kind: 'schema', requestId: 'req_schema' })
  })
})
```

- [ ] Create Zod schemas with refinements that exactly match the approved limits. `TelemetryHistoryQuerySchema` rejects `raw` requests above 5,000, bucketed requests above 2,000, and time ranges where `from >= to`; acknowledgement responses require `status: 'acknowledged'`; resolution responses require `status: 'resolved'`.
- [ ] Use the following adapter pattern for all query values. It keeps backend URLs out of pages and keeps the protocol relative.

```ts
// frontend/src/api/telemetry.ts
import { z } from 'zod'
import { requestJson } from './http'
import { SensorIdSchema, Rfc3339Schema, BucketSchema } from '../contracts/common'

const LatestTelemetryResponseSchema = z.object({ request_id: z.string(), generated_at: Rfc3339Schema, sensors: z.array(z.object({ device_id: SensorIdSchema, ts: Rfc3339Schema.nullable(), temperature_c: z.number().nullable(), relative_humidity_pct: z.number().nullable(), freshness: z.enum(['fresh', 'stale', 'unknown']), age_seconds: z.number().nonnegative().nullable(), availability: z.enum(['online', 'offline', 'unknown']) })) })
export type LatestTelemetryResponse = z.infer<typeof LatestTelemetryResponseSchema>

export async function getLatestTelemetry(deviceId?: z.infer<typeof SensorIdSchema>, signal?: AbortSignal): Promise<LatestTelemetryResponse> {
  const query = new URLSearchParams(deviceId ? { device_id: deviceId } : {})
  return requestJson(`/api/telemetry/latest${query.size ? `?${query}` : ''}` as `/api/${string}`, LatestTelemetryResponseSchema, { signal })
}

export const TelemetryHistoryQuerySchema = z.object({ deviceId: SensorIdSchema, from: Rfc3339Schema, to: Rfc3339Schema, bucket: BucketSchema.default('raw'), limit: z.number().int().min(1).max(5_000).default(500), cursor: z.string().optional() }).superRefine((value, ctx) => {
  if (Date.parse(value.from) >= Date.parse(value.to)) ctx.addIssue({ code: 'custom', message: 'from must be earlier than to', path: ['from'] })
  if (value.bucket !== 'raw' && value.limit > 2_000) ctx.addIssue({ code: 'custom', message: 'bucketed limit must be at most 2000', path: ['limit'] })
})
```

- [ ] Run `npm test -- src/contracts/contracts.test.ts src/api/api.test.ts`; expect all contract and adapter tests to pass.
- [ ] Run `npm run lint && npm run build`; expect exit 0, no unsafe `any`, no absolute backend host, and no `fetch(` outside `src/api/http.ts`.

**Acceptance:** all responses are runtime-validated with Zod before pages see them; list bounds and errors match the specification; lifecycle adapters accept caller-created command bodies and never create IDs internally.

## Task 3: Deterministic MSW

**Depends on:** Task 2. **Consumes:** typed contracts and adapters. **Produces:** shared browser and Node handlers, eight deterministic scenarios, mutable test-local lifecycle state, and production MSW exclusion.

**Files:** Create `frontend/public-dev/mockServiceWorker.js`, `frontend/src/mocks/scenario.ts`, `state.ts`, `handlers.ts`, `browser.ts`, `node.ts`, `handlers.test.ts`, `fixtures/telemetry.ts`, `fixtures/inference.ts`, `fixtures/alerts.ts`, `fixtures/eda.ts`, `fixtures/modelEvaluations.ts`, and `fixtures/systemHealth.ts`. Modify `frontend/src/main.tsx`, `frontend/src/test/setup.ts`, and `frontend/vite.config.ts`.

**Interfaces:**

```ts
// frontend/src/mocks/scenario.ts
export type MockScenario = 'normal' | 'active-anomaly' | 'stale' | 'offline' | 'data-gap' | 'empty' | 'timeout' | 'server-error'
export function scenarioFromSearch(search: string): MockScenario {
  const value = new URLSearchParams(search).get('__scenario')
  return value === 'active-anomaly' || value === 'stale' || value === 'offline' || value === 'data-gap' || value === 'empty' || value === 'timeout' || value === 'server-error' ? value : 'normal'
}

// frontend/src/mocks/state.ts
export interface MockApiState { scenario: MockScenario; events: AlertEvent[]; acceptedCommands: Map<string, AlertMutationResponse> }
export declare function resetMockState(scenario?: MockScenario): void
export declare function setMockScenario(scenario: MockScenario): void

// frontend/src/mocks/handlers.ts
export declare function createHandlers(state: MockApiState): HttpHandler[]
```

`AlertEvent` and `AlertMutationResponse` are exports from `src/contracts/alerts.ts`. Fixture timestamps, IDs, cursor values, order, and request IDs are constants. Normal returns fresh six-sensor data and no active alerts. Active anomaly returns active `n4`, a score threshold breach, and acknowledgement action. Stale, offline, gap, empty, timeout, and server error retain their precise spec meanings.

| Scenario | Exact handler result |
|---|---|
| `normal` | All six sensors are fresh, bounded history and scores are normal, no active alert exists, EDA/evaluation data exists, and system services are ready. |
| `active-anomaly` | `n4` has a threshold breach, active current alert, score-lane marker, and acknowledgement action. |
| `stale` | The selected sensor has a valid old timestamp and `freshness: 'stale'`; unaffected panels remain available. |
| `offline` | The selected latest telemetry response has `availability: 'offline'`, `freshness: 'unknown'`, and last timestamp/age when known. |
| `data-gap` | History has a missing interval preceded by `gap_before: true`; no derived point bridges it. |
| `empty` | Valid empty arrays and zero counts return for the selected filter. |
| `timeout` | The handler delays long enough for the client’s 8-second abort path to run. |
| `server-error` | The selected endpoint returns fixed Problem Details with a fixed `request_id`. |

- [ ] Create handler tests for every endpoint under all named scenarios, then add lifecycle tests for direct active resolve 409, acknowledge append, resolve only after acknowledgement, immutable ordered history, idempotent replay, conflicting reuse of a command ID, and state reset.
- [ ] Run `npm test -- src/mocks/handlers.test.ts`; expect missing mock modules.

```ts
// frontend/src/mocks/handlers.test.ts
import { afterEach, describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from './node'
import { resetMockState, setMockScenario } from './state'

afterEach(() => { server.resetHandlers(); resetMockState() })

describe('active anomaly lifecycle', () => {
  it('rejects resolving an active alert', async () => {
    setMockScenario('active-anomaly')
    const response = await fetch('/api/alerts/alert_n4_active/resolve', { method: 'POST', body: JSON.stringify({ command_id: '550e8400-e29b-41d4-a716-446655440000', event_ts: '2026-07-19T10:31:00Z' }) })
    expect(response.status).toBe(409)
    await expect(response.json()).resolves.toMatchObject({ request_id: 'req_direct_resolve', status: 409 })
  })
})
```

- [ ] Generate the worker with `npx msw init public-dev --save`; expect `public-dev/mockServiceWorker.js` and the worker-directory setting saved in package metadata.
- [ ] Create fixtures that use `n1` through `n6`, fixed `2026-07-19T...Z` timestamps, `gap_before: true` before a missing interval, and active alert `alert_n4_active` only in active-anomaly state.
- [ ] Wire Node MSW so tests fail on unhandled requests and reset state after each test.

```ts
// frontend/src/mocks/state.ts
import type { AlertEvent, AlertMutationResponse } from '../contracts/alerts'
import type { MockScenario } from './scenario'
export const mockState: MockApiState = { scenario: 'normal', events: [], acceptedCommands: new Map<string, AlertMutationResponse>() }
export function resetMockState(scenario: MockScenario = 'normal') { mockState.scenario = scenario; mockState.events = []; mockState.acceptedCommands.clear() }
export function setMockScenario(scenario: MockScenario) { resetMockState(scenario) }

// frontend/src/mocks/node.ts and frontend/src/test/setup.ts
import { setupServer } from 'msw/node'
import { createHandlers } from './handlers'
import { mockState, resetMockState } from './state'

export const server = setupServer(...createHandlers(mockState))

// frontend/src/test/setup.ts
import '@testing-library/jest-dom/vitest'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { server } from '../mocks/node'
import { resetMockState } from '../mocks/state'
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => { server.resetHandlers(); resetMockState() })
afterAll(() => server.close())
```

```ts
// frontend/src/mocks/browser.ts
import { setupWorker } from 'msw/browser'
import { createHandlers } from './handlers'
import { mockState, setMockScenario } from './state'
import { scenarioFromSearch } from './scenario'
const worker = setupWorker(...createHandlers(mockState))
export async function startBrowserMocks() { setMockScenario(scenarioFromSearch(window.location.search)); await worker.start({ onUnhandledRequest: 'error' }) }
```

- [ ] Start browser mocks only through a development-only dynamic import, after page load can read `__scenario`.

```ts
// frontend/src/main.tsx
async function start() {
  if (import.meta.env.DEV) {
    const { startBrowserMocks } = await import('./mocks/browser')
    await startBrowserMocks()
  }
  const { createRoot } = await import('react-dom/client')
  const { App } = await import('./app/App')
  createRoot(document.getElementById('root')!).render(<App />)
}
void start()

// frontend/vite.config.ts, relevant public handling
export default defineConfig(({ command }) => ({ publicDir: command === 'serve' ? 'public-dev' : false }))
```

- [ ] Run `npm test -- src/mocks/handlers.test.ts`; expect all eight scenarios and lifecycle cases to pass.
- [ ] Run `npm run build && test ! -e dist/mockServiceWorker.js`; expect build success and shell exit 0.

**Acceptance:** browser and Node tests share handler logic; active anomaly starts with active `n4`; stale and offline differ semantically; timeout is observably slower than the 8-second client timeout; no standalone mock server or production mock artifact exists.

## Task 4: URL filters and query hooks

**Depends on:** Tasks 2 and 3. **Consumes:** adapters, contracts, MSW. **Produces:** canonical URL parsing, normalized query keys, polling, stale preservation, cancellation, and lifecycle retry identity.

**Files:** Create `frontend/src/app/queryClient.ts`, `frontend/src/features/filters/*`, `frontend/src/features/{telemetry,inference,alerts,eda,modelEvaluation,systemHealth}/*` query paths. Modify `frontend/src/app/AppProviders.tsx`.

**Interfaces:**

```ts
// frontend/src/features/filters/urlFilters.ts
import type { Bucket, SensorId } from '../../contracts/common'
export interface UrlFilters { sensor?: SensorId; from: string; to: string; bucket: Bucket; modelVersion?: string }
export declare function parseUrlFilters(params: URLSearchParams, routeSensorId?: string): UrlFilters
export declare function updateUrlFilters(current: URLSearchParams, patch: Partial<UrlFilters>): URLSearchParams

// frontend/src/features/alerts/alertCommand.ts
import type { AlertCommandRequest } from '../../contracts/common'
export interface AlertLifecycleCommand { alertId: string; action: 'acknowledge' | 'resolve'; body: AlertCommandRequest }
export declare function createAlertLifecycleCommand(alertId: string, action: 'acknowledge' | 'resolve', note?: string): AlertLifecycleCommand
```

**Query contracts:** `useLatestTelemetryQuery` and `useCurrentAlertsQuery` use `refetchInterval: 10_000`; `useSystemStatusQuery` uses `refetchInterval: 30_000`; history, inference, all EDA, and evaluation queries omit `refetchInterval`. Every `queryFn` receives and forwards TanStack Query’s `signal`. Query keys contain normalized strings and primitive values only.

- [ ] Create tests for restoring all five URL keys, invalid sensor, invalid bucket, missing timezone, reversed time range, route-sensor precedence, no background polling for histories, 10-second telemetry and alert polls, 30-second system poll, stale-result retention after refetch error, and identical lifecycle retry variables.
- [ ] Run `npm test -- src/features/filters/urlFilters.test.ts src/features/telemetry/queries.test.tsx src/features/alerts/lifecycle.test.tsx`; expect missing exports.

```ts
// frontend/src/features/filters/urlFilters.ts
import { BucketSchema, SensorIdSchema, Rfc3339Schema, type SensorId, type Bucket } from '../../contracts/common'

const defaults = { from: '2026-07-18T00:00:00Z', to: '2026-07-19T00:00:00Z', bucket: '15m' as Bucket }
export function parseUrlFilters(params: URLSearchParams, routeSensorId?: string) {
  const routeSensor = SensorIdSchema.safeParse(routeSensorId)
  const querySensor = SensorIdSchema.safeParse(params.get('sensor'))
  const from = Rfc3339Schema.safeParse(params.get('from')).success ? params.get('from')! : defaults.from
  const to = Rfc3339Schema.safeParse(params.get('to')).success ? params.get('to')! : defaults.to
  const bucket = BucketSchema.safeParse(params.get('bucket')).success ? BucketSchema.parse(params.get('bucket')) : defaults.bucket
  return { sensor: routeSensor.success ? routeSensor.data : querySensor.success ? querySensor.data : undefined, from: Date.parse(from) < Date.parse(to) ? from : defaults.from, to: Date.parse(from) < Date.parse(to) ? to : defaults.to, bucket, modelVersion: params.get('model_version') || undefined }
}

export function updateUrlFilters(current: URLSearchParams, patch: Partial<{ sensor?: SensorId; from: string; to: string; bucket: Bucket; modelVersion?: string }>) {
  const next = new URLSearchParams(current)
  const values: Record<string, string | undefined> = { sensor: patch.sensor, from: patch.from, to: patch.to, bucket: patch.bucket, model_version: patch.modelVersion }
  for (const [key, value] of Object.entries(values)) value ? next.set(key, value) : value === undefined ? undefined : next.delete(key)
  return next
}
```

```ts
// frontend/src/features/alerts/useAlertLifecycleMutation.ts
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { acknowledgeAlert, resolveAlert } from '../../api/alerts'
import type { AlertLifecycleCommand } from './alertCommand'

export function useAlertLifecycleMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ alertId, action, body }: AlertLifecycleCommand) => action === 'acknowledge' ? acknowledgeAlert(alertId, body) : resolveAlert(alertId, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['alerts', 'current'] }),
    onError: () => queryClient.invalidateQueries({ queryKey: ['alerts', 'current'] }),
  })
}
```

- [ ] Create `createAlertLifecycleCommand` with `crypto.randomUUID()` and one `new Date().toISOString()` call. Pages call it once before `mutate`; `mutation.reset()` does not recreate variables; retry calls `mutate(mutation.variables!)`.
- [ ] Run the targeted command again; expect URL, polling, cancellation, stale preservation, and identity tests to pass.

**Acceptance:** URL reload restores controls and requests; invalid values normalize before request; query keys are normalized; no optimistic row transition occurs; conflict handling refetches confirmed server state.

## Task 5: Shared state components

**Depends on:** Task 2. **Consumes:** `ApiError`, contract enums, URL filter type. **Produces:** reusable loading, empty, error, polling-failure, status, temporal-filter, and table-alternative components.

**Files:** Create `frontend/src/components/states/PanelSkeleton.tsx`, `EmptyState.tsx`, `ApiErrorPanel.tsx`, `PollingFailureNotice.tsx`, `SensorStatus.tsx`, `states.test.tsx`, `frontend/src/components/filters/TemporalFilterBar.tsx`, `TemporalFilterBar.test.tsx`, `frontend/src/components/data/BoundedDataDialog.tsx`, and `BoundedDataDialog.test.tsx`.

**Interfaces:**

```ts
export interface ApiErrorPanelProps { error: ApiError; onRetry: () => void }
export interface PollingFailureNoticeProps { resource: string; lastUpdated: string; onRetry: () => void }
export interface SensorStatusProps { freshness: Freshness; availability: Availability; ageSeconds?: number; timestamp?: string }
export interface TemporalFilterBarProps { value: Pick<UrlFilters, 'sensor' | 'from' | 'to' | 'bucket'>; onChange: (patch: Partial<UrlFilters>) => void; allowAllSensors?: boolean }
export interface BoundedDataDialogProps<Row> { open: boolean; title: string; rows: readonly Row[]; returnedCount: number; columns: readonly GridColDef<Row>[]; onClose: () => void }
```

- [ ] Create red role and keyboard tests for skeleton, empty state, Problem Details plus request ID, polling failure, stale, offline, unknown, temporal controls, and `Lihat data` dialog.
- [ ] Run `npm test -- src/components/states/states.test.tsx src/components/filters/TemporalFilterBar.test.tsx src/components/data/BoundedDataDialog.test.tsx`; expect missing-component failures.

```tsx
// frontend/src/components/states/SensorStatus.tsx
import { Chip, Stack, Typography } from '@mui/material'
import type { Availability, Freshness } from '../../contracts/common'
export interface SensorStatusProps { freshness: Freshness; availability: Availability; ageSeconds?: number; timestamp?: string }

export function SensorStatus({ freshness, availability, ageSeconds, timestamp }: SensorStatusProps) {
  const text = availability === 'offline' ? 'Offline sensor' : freshness === 'stale' ? 'Stale telemetry' : freshness === 'fresh' ? 'Fresh telemetry' : 'Current status unknown'
  return <Stack spacing={0.5}><Chip label={text} color={availability === 'offline' ? 'error' : freshness === 'stale' ? 'warning' : 'default'} /><Typography variant="caption">{timestamp ?? 'No last telemetry timestamp'}{ageSeconds === undefined ? '' : `, age ${ageSeconds} seconds`}</Typography></Stack>
}

// frontend/src/components/states/ApiErrorPanel.tsx
import { Alert, Button } from '@mui/material'
import type { ApiError } from '../../api/errors'
export interface ApiErrorPanelProps { error: ApiError; onRetry: () => void }
export function ApiErrorPanel({ error, onRetry }: ApiErrorPanelProps) {
  return <Alert severity="error" action={<Button onClick={onRetry}>Retry</Button>}><strong>{error.problem?.title ?? 'Data request failed'}</strong><br />{error.problem?.detail ?? error.message}{error.requestId ? <><br />Request ID: {error.requestId}</> : null}</Alert>
}
```

```tsx
// frontend/src/components/data/BoundedDataDialog.tsx
import { Dialog, DialogContent, DialogTitle, Typography } from '@mui/material'
import { DataGrid, type GridColDef } from '@mui/x-data-grid'
export interface BoundedDataDialogProps<Row> { open: boolean; title: string; rows: readonly Row[]; returnedCount: number; columns: readonly GridColDef<Row>[]; onClose: () => void }
export function BoundedDataDialog<Row extends { id: string }>({ open, title, rows, returnedCount, columns, onClose }: BoundedDataDialogProps<Row>) {
  return <Dialog open={open} onClose={onClose} fullWidth maxWidth="lg"><DialogTitle>{title}</DialogTitle><DialogContent><Typography>{returnedCount} bounded records returned</Typography><DataGrid rows={[...rows]} columns={[...columns] as GridColDef<Row>[]} autoHeight disableRowSelectionOnClick /></DialogContent></Dialog>
}
```

- [ ] Ensure controls have labels `Sensor`, `From`, `To`, and `Bucket`; the data alternative button has accessible name `Lihat data`.
- [ ] Run the targeted command; expect roles, names, focus, row equality, request ID, and stale/offline distinction tests to pass.

**Acceptance:** filters stay visible during empty/error states; status never relies on color alone; every chart caller can show its same bounded rows through the dialog.

## Task 6: ECharts primitives

**Depends on:** Tasks 1 and 2. **Consumes:** MUI theme and contract point types. **Produces:** a disposal-safe ECharts component, MUI-token chart theme, and pure temporal/EDA/evaluation option builders.

**Files:** Create `frontend/src/components/charts/EChart.tsx`, `EChart.test.tsx`, `temporalOptions.ts`, `edaOptions.ts`, `evaluationOptions.ts`, and `options.test.ts`. Modify `frontend/src/theme/echartsTheme.ts` created in Task 1.

**Interfaces:**

```ts
export interface EChartProps { option: EChartsOption; ariaLabel: string; height: number }
export interface TemporalChartInput { theme: Theme; sensorId: SensorId; from: string; to: string; telemetry: readonly TelemetryPoint[]; inference: readonly InferencePoint[]; alerts: readonly AlertEvent[] }
export declare function buildTemporalOptions(input: TemporalChartInput): EChartsOption
export declare function buildTemporalSummary(input: TemporalChartInput): string
export declare function buildHistogramOptions(input: HistogramResponse): EChartsOption
export declare function buildScatterOptions(input: CorrelationResponse): EChartsOption
export declare function buildConfusionMatrixOptions(input: ConfusionMatrix): EChartsOption
export declare function buildRocOptions(input: RocCurve): EChartsOption
export declare function buildPrecisionRecallOptions(input: PrecisionRecallCurve): EChartsOption
```

- [ ] Create option tests first: exactly three vertically aligned grids, three Y axes, linked X-axis pointer and data zoom, straight lines, `connectNulls: false`, dashed threshold, anomaly markers or intervals, no gradients, no third Y axis, `animation: false`, MUI token colors/fonts, and ARIA text naming sensor/range/gaps/threshold/anomalies.
- [ ] Create wrapper tests for init, resize, set option, and dispose.
- [ ] Run `npm test -- src/components/charts/options.test.ts src/components/charts/EChart.test.tsx`; expect missing builder/wrapper failures.

```ts
// frontend/src/components/charts/temporalOptions.ts
import type { EChartsOption } from 'echarts'
import type { Theme } from '@mui/material/styles'
import type { SensorId } from '../../contracts/common'
import type { TelemetryPoint } from '../../contracts/telemetry'
import type { InferencePoint } from '../../contracts/inference'
import type { AlertEvent } from '../../contracts/alerts'
export interface TemporalChartInput { theme: Theme; sensorId: SensorId; from: string; to: string; telemetry: readonly TelemetryPoint[]; inference: readonly InferencePoint[]; alerts: readonly AlertEvent[] }
export function buildTemporalOptions({ theme, sensorId, from, to, telemetry, inference, alerts }: TemporalChartInput): EChartsOption {
  const temperatures = telemetry.map(point => [point.ts, point.temperature_c])
  const humidities = telemetry.map(point => [point.ts, point.relative_humidity_pct])
  const scores = inference.map(point => [point.window_end_ts, point.score])
  const threshold = inference[0]?.threshold
  return {
    animation: false,
    aria: { enabled: true, description: `${sensorId}, ${from} to ${to}. ${telemetry.filter(point => point.gap_before).length} documented gaps. ${threshold === undefined ? 'No score threshold available.' : `Score threshold ${threshold}.`} ${alerts.filter(event => event.event_type === 'detected').length} anomaly markers.` },
    color: [theme.palette.primary.main, theme.palette.info.main, theme.palette.warning.main],
    textStyle: { color: theme.palette.text.primary, fontFamily: theme.typography.fontFamily },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    dataZoom: [{ type: 'inside', xAxisIndex: [0, 1, 2] }, { type: 'slider', xAxisIndex: [0, 1, 2] }],
    grid: [{ left: 64, right: 24, top: 32, height: '22%' }, { left: 64, right: 24, top: '39%', height: '22%' }, { left: 64, right: 24, top: '68%', height: '22%' }],
    xAxis: [0, 1, 2].map((gridIndex) => ({ type: 'time', gridIndex, axisLabel: { show: gridIndex === 2 } })),
    yAxis: [{ type: 'value', gridIndex: 0, name: 'Temperature °C' }, { type: 'value', gridIndex: 1, name: 'Relative humidity %' }, { type: 'value', gridIndex: 2, name: 'Anomaly score' }],
    series: [
      { name: 'Temperature °C', type: 'line', xAxisIndex: 0, yAxisIndex: 0, smooth: false, connectNulls: false, showSymbol: false, data: temperatures },
      { name: 'Relative humidity %', type: 'line', xAxisIndex: 1, yAxisIndex: 1, smooth: false, connectNulls: false, showSymbol: false, data: humidities },
      { name: 'Anomaly score', type: 'line', xAxisIndex: 2, yAxisIndex: 2, smooth: false, connectNulls: false, showSymbol: false, data: scores, markLine: threshold === undefined ? undefined : { symbol: 'none', lineStyle: { type: 'dashed' }, data: [{ yAxis: threshold, name: 'Threshold' }] } },
    ],
  }
}
```

- [ ] Run the targeted command again; expect all chart rules and lifecycle tests to pass.

**Acceptance:** Apache ECharts is the only chart library. Charts show textual labels and summaries, preserve gaps, do not use smoothed curves, gradient decoration, point clutter, interpolation, or a third Y axis.

## Task 7: Overview

**Depends on:** Tasks 3, 4, 5. **Consumes:** `useLatestTelemetryQuery`, `useCurrentAlertsQuery`, `useOverviewData`, `SensorStatus`, `ActionQueue`. **Produces:** action-first six-sensor triage with current alert acknowledgement.

**Files:** Modify `frontend/src/pages/OverviewPage.tsx`; create `frontend/src/pages/OverviewPage.test.tsx`, `frontend/src/features/overview/useOverviewData.ts`, `ActionQueue.tsx`, `CurrentAlertCard.tsx`, and `SensorMatrix.tsx`.

**Interfaces:**

```ts
export interface LatestSensorScore { deviceId: SensorId; score?: number; threshold?: number; isAnomaly?: boolean }
export declare function useOverviewData(): { latestTelemetry: UseQueryResult<LatestTelemetryResponse, ApiError>; currentAlerts: UseQueryResult<CurrentAlertsResponse, ApiError>; latestScores: readonly LatestSensorScore[] }
```

`useOverviewData` starts one bounded inference-history request per sensor, uses the last returned point as score, and never polls those scores.

- [ ] Create active-anomaly tests that find six sensor cards by `article` role and accessible names `Sensor n1` through `Sensor n6`, see `n4` priority text, freshness, score, age, active count, sensor/history links, and an `Acknowledge alert` button.
- [ ] Create independent telemetry/alert loading-error tests and stale/offline distinction tests. Assert no `Resolve alert`, no raw telemetry grid, no full EDA content, and no evaluation report on this page.
- [ ] Run `npm test -- src/pages/OverviewPage.test.tsx`; expect the heading-only route module to fail triage-content assertions.

```tsx
// frontend/src/pages/OverviewPage.tsx
import { Alert, Button, Link, Stack, Typography } from '@mui/material'
import { Link as RouterLink } from 'react-router-dom'
import { PanelSkeleton } from '../components/states/PanelSkeleton'
import { PollingFailureNotice } from '../components/states/PollingFailureNotice'
import { SensorStatus } from '../components/states/SensorStatus'
import { useOverviewData } from '../features/overview/useOverviewData'
import { ActionQueue } from '../features/overview/ActionQueue'

export function OverviewPage() {
  const { latestTelemetry, currentAlerts, latestScores } = useOverviewData()
  if (latestTelemetry.isLoading) return <PanelSkeleton label="Loading sensor overview" />
  if (!latestTelemetry.data) return <Alert severity="error">Sensor overview is unavailable</Alert>
  const active = currentAlerts.data?.items.filter(item => item.status === 'detected') ?? []
  return <Stack spacing={3}><Typography variant="h1">Overview</Typography><Typography>{active.length} active alerts need attention</Typography>{currentAlerts.isError ? <PollingFailureNotice resource="current alerts" lastUpdated={latestTelemetry.data.generated_at} onRetry={() => void currentAlerts.refetch()} /> : null}<Stack direction="row" flexWrap="wrap" gap={2}>{latestTelemetry.data.sensors.map(sensor => {
    const score = latestScores.find(item => item.deviceId === sensor.device_id)
    return <article key={sensor.device_id} aria-label={`Sensor ${sensor.device_id}`}><Typography variant="h2">Sensor {sensor.device_id}</Typography><SensorStatus freshness={sensor.freshness} availability={sensor.availability} ageSeconds={sensor.age_seconds ?? undefined} timestamp={sensor.ts ?? undefined} /><Typography>Temperature: {sensor.temperature_c ?? 'Unavailable'} °C</Typography><Typography>RH: {sensor.relative_humidity_pct ?? 'Unavailable'} %</Typography><Typography>Score: {score?.score ?? 'No score available'}</Typography><Link component={RouterLink} to={`/sensors/${sensor.device_id}?sensor=${sensor.device_id}`}>Inspect sensor history</Link></article>
  })}</Stack>{active.map(alert => <Alert key={alert.alert_id} severity="warning" action={<Button component={RouterLink} to={`/alerts?sensor=${alert.device_id}`}>Review alert</Button>}>Active alert for {alert.device_id}<ActionQueue alert={alert} /></Alert>)}</Stack>
}
```

```tsx
// frontend/src/features/overview/ActionQueue.tsx
import { Button } from '@mui/material'
import type { CurrentAlert } from '../../contracts/alerts'
import { createAlertLifecycleCommand } from '../alerts/alertCommand'
import { useAlertLifecycleMutation } from '../alerts/useAlertLifecycleMutation'
export function ActionQueue({ alert }: { alert: CurrentAlert }) {
  const mutation = useAlertLifecycleMutation()
  if (alert.status !== 'detected') return null
  const command = () => mutation.mutate(createAlertLifecycleCommand(alert.alert_id, 'acknowledge'))
  return <>{mutation.isError && mutation.variables ? <Button onClick={() => mutation.mutate(mutation.variables)}>Retry acknowledgement</Button> : null}<Button onClick={command} disabled={mutation.isPending}>Acknowledge alert</Button></>
}
```

- [ ] Run `npm test -- src/pages/OverviewPage.test.tsx`; expect the triage/state tests to pass.

**Acceptance:** all six sensors appear; active `n4` receives visual and textual priority; active alerts can acknowledge but cannot resolve; polling failure preserves prior values.

## Task 8: Sensor Detail and History

**Depends on:** Tasks 3, 4, 5, 6. **Consumes:** route sensor, URL filters, `TemporalFilterBar`, history/inference/alert hooks, `EChart`, `buildTemporalOptions`, state components, bounded dialog. **Produces:** independent telemetry, inference, alert-context panels and the same-records table alternative.

**Files:** Modify `frontend/src/pages/SensorDetailPage.tsx`; create `frontend/src/pages/SensorDetailPage.test.tsx`; create `frontend/src/features/sensors/SensorHistoryPanel.tsx` and `RelatedAlertHistory.tsx`.

**Interfaces:**

```ts
export interface SensorHistoryPanelProps { sensorId: SensorId; filters: UrlFilters }
export interface RelatedAlertHistoryProps { sensorId: SensorId; from: string; to: string }
```

- [ ] Create tests for valid `:sensorId`, invalid `:sensorId` redirect to `/`, route-sensor precedence, restored `sensor/from/to/bucket`, preserved `gap_before`, independent panel errors with request IDs and retry buttons, and `Lihat data` rows equal to the bounded history/inference response rows.
- [ ] Assert DOM contracts: heading `Sensor Detail & History`; controls named `Sensor`, `From`, `To`, `Bucket`; region `Telemetry and inference history`; button `Lihat data`; and each failed panel’s `Retry` button.
- [ ] Run `npm test -- src/pages/SensorDetailPage.test.tsx`; expect the heading-only route module to fail panel-content assertions.

```tsx
// frontend/src/pages/SensorDetailPage.tsx
import { Button, Stack, Typography } from '@mui/material'
import { Navigate, useParams, useSearchParams } from 'react-router-dom'
import { SensorIdSchema } from '../contracts/common'
import { parseUrlFilters, updateUrlFilters } from '../features/filters/urlFilters'
import { SensorHistoryPanel } from '../features/sensors/SensorHistoryPanel'
import { RelatedAlertHistory } from '../features/sensors/RelatedAlertHistory'
import { TemporalFilterBar } from '../components/filters/TemporalFilterBar'

export function SensorDetailPage() {
  const { sensorId: rawSensorId } = useParams()
  const [params, setParams] = useSearchParams()
  const parsed = SensorIdSchema.safeParse(rawSensorId)
  if (!parsed.success) return <Navigate to="/" replace />
  const filters = parseUrlFilters(params, parsed.data)
  return <Stack spacing={3}><Typography variant="h1">Sensor Detail & History</Typography><Typography>Selected sensor: {parsed.data}</Typography><TemporalFilterBar value={{ ...filters, sensor: parsed.data }} onChange={(patch) => setParams(updateUrlFilters(params, patch))} /><SensorHistoryPanel sensorId={parsed.data} filters={filters} /><RelatedAlertHistory sensorId={parsed.data} from={filters.from} to={filters.to} /></Stack>
}
```

```tsx
// frontend/src/features/sensors/SensorHistoryPanel.tsx
import { Button } from '@mui/material'
import { useState } from 'react'
import { useTheme } from '@mui/material/styles'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import { BoundedDataDialog } from '../../components/data/BoundedDataDialog'
import { EChart } from '../../components/charts/EChart'
import { buildTemporalOptions } from '../../components/charts/temporalOptions'
import { useTelemetryHistoryQuery } from '../telemetry/queries'
import { useInferenceResultsQuery } from '../inference/queries'
import type { SensorId } from '../../contracts/common'
import type { UrlFilters } from '../filters/urlFilters'
export interface SensorHistoryPanelProps { sensorId: SensorId; filters: UrlFilters }
const telemetryColumns = [{ field: 'ts', headerName: 'Timestamp', flex: 1 }, { field: 'temperature_c', headerName: 'Temperature °C', flex: 1 }, { field: 'relative_humidity_pct', headerName: 'Relative humidity %', flex: 1 }]
export function SensorHistoryPanel({ sensorId, filters }: SensorHistoryPanelProps) {
  const [open, setOpen] = useState(false)
  const theme = useTheme()
  const telemetry = useTelemetryHistoryQuery({ deviceId: sensorId, from: filters.from, to: filters.to, bucket: filters.bucket, limit: filters.bucket === 'raw' ? 5_000 : 2_000 })
  const inference = useInferenceResultsQuery({ deviceId: sensorId, from: filters.from, to: filters.to, bucket: filters.bucket, limit: filters.bucket === 'raw' ? 5_000 : 2_000, modelVersion: filters.modelVersion })
  if (telemetry.isError) return <ApiErrorPanel error={telemetry.error} onRetry={() => void telemetry.refetch()} />
  if (!telemetry.data) return <PanelSkeleton label="Loading telemetry history" />
  const option = buildTemporalOptions({ theme, sensorId, from: filters.from, to: filters.to, telemetry: telemetry.data.points, inference: inference.data?.points ?? [], alerts: [] })
  return <section aria-label="Telemetry and inference history"><EChart option={option} ariaLabel={`History chart for ${sensorId}`} height={620} /><Button onClick={() => setOpen(true)}>Lihat data</Button><BoundedDataDialog open={open} title={`History data for ${sensorId}`} rows={telemetry.data.points.map(point => ({ id: point.ts, ...point }))} returnedCount={telemetry.data.returned_count} columns={telemetryColumns} onClose={() => setOpen(false)} /></section>
}
```

- [ ] Run `npm test -- src/pages/SensorDetailPage.test.tsx src/components/charts/options.test.ts`; expect all tests to pass.

**Acceptance:** route sensor is authoritative; cross-page links carry `sensor`; history never background-polls; valid sibling panels remain visible when one fails; chart and table use the same bounded data.

## Task 9: Alerts

**Depends on:** Tasks 3, 4, 5. **Consumes:** current-alert, event-history, and lifecycle hooks; `DataGrid` Community; shared state/filter components. **Produces:** filterable paginated current-state grid, immutable history, and strict actions.

**Files:** Modify `frontend/src/pages/AlertsPage.tsx`; create `frontend/src/pages/AlertsPage.test.tsx`, `frontend/src/features/alerts-ui/AlertsGrid.tsx`, `AlertEventHistory.tsx`, and `AlertLifecycleActions.tsx`.

**Interfaces:**

```ts
export interface AlertsGridProps { response: CurrentAlertsResponse; page: number; onPageChange: (page: number) => void; onSelectAlert: (alertId: string) => void }
export interface AlertEventHistoryProps { alertId?: string; deviceId?: SensorId; from: string; to: string }
export interface AlertLifecycleActionsProps { alert: CurrentAlert }
```

`from` and `to` filter `GET /api/alert-events`, not `GET /api/alerts/current`.

- [ ] Create tests for labeled sensor/status/time controls, Data Grid pagination, 100 page-size ceiling, keyboard row selection, immutable ordered event history, active acknowledge-only controls, acknowledged resolve control, resolved no-action state, pessimistic pending row state, identical failed-action retry body, and 409 refresh explanation.
- [ ] Assert DOM contracts: heading `Alerts`; grid label `Current alerts`; filters `Sensor`, `Status`, `From`, and `To`; buttons `Acknowledge alert`, `Resolve alert`, and `Retry action` only in their permitted lifecycle states.
- [ ] Run `npm test -- src/pages/AlertsPage.test.tsx src/features/alerts/lifecycle.test.tsx`; expect missing grid/action modules.

```tsx
// frontend/src/features/alerts-ui/AlertLifecycleActions.tsx
import { Button, Stack } from '@mui/material'
import { createAlertLifecycleCommand } from '../alerts/alertCommand'
import { useAlertLifecycleMutation } from '../alerts/useAlertLifecycleMutation'
import type { CurrentAlert } from '../../contracts/alerts'
export interface AlertLifecycleActionsProps { alert: CurrentAlert }

export function AlertLifecycleActions({ alert }: AlertLifecycleActionsProps) {
  const mutation = useAlertLifecycleMutation()
  const send = (action: 'acknowledge' | 'resolve') => mutation.mutate(createAlertLifecycleCommand(alert.alert_id, action))
  const retry = () => { if (mutation.variables) mutation.mutate(mutation.variables) }
  return <Stack direction="row" spacing={1}>{alert.status === 'detected' ? <Button disabled={mutation.isPending} onClick={() => send('acknowledge')}>Acknowledge alert</Button> : null}{alert.status === 'acknowledged' ? <Button disabled={mutation.isPending} onClick={() => send('resolve')}>Resolve alert</Button> : null}{mutation.isError ? <Button onClick={retry}>Retry action</Button> : null}</Stack>
}
```

```tsx
// frontend/src/features/alerts-ui/AlertsGrid.tsx
import { DataGrid, type GridColDef } from '@mui/x-data-grid'
import type { CurrentAlert, CurrentAlertsResponse } from '../../contracts/alerts'
export interface AlertsGridProps { response: CurrentAlertsResponse; page: number; onPageChange: (page: number) => void; onSelectAlert: (alertId: string) => void }
const columns: GridColDef<CurrentAlert>[] = [{ field: 'alert_id', headerName: 'Alert ID', flex: 1 }, { field: 'device_id', headerName: 'Sensor', flex: 1 }, { field: 'status', headerName: 'Status', flex: 1 }, { field: 'latest_event_ts', headerName: 'Last event', flex: 1 }]
export function AlertsGrid({ response, page, onPageChange, onSelectAlert }: AlertsGridProps) {
  return <DataGrid aria-label="Current alerts" rows={response.items} columns={columns} getRowId={(row) => row.alert_id} rowCount={response.total} paginationMode="server" paginationModel={{ page, pageSize: response.page_size }} pageSizeOptions={[10, 25, 50, 100]} onPaginationModelChange={(model) => onPageChange(model.page)} onRowClick={(params) => onSelectAlert(params.row.alert_id)} />
}
```

- [ ] Run `npm test -- src/pages/AlertsPage.test.tsx src/features/alerts/lifecycle.test.tsx`; expect pass.

**Acceptance:** current alert state cannot skip lifecycle stages; direct active resolve is unavailable; the UI makes no optimistic transition; history remains append-only; only Community Data Grid APIs appear.

## Task 10: EDA

**Depends on:** Tasks 3, 4, 5, 6. **Consumes:** EDA and temporal hooks, URL filters, ECharts builders, state components. **Produces:** seven bounded examiner-facing panels with independent failure states.

**Files:** Modify `frontend/src/pages/EdaPage.tsx`, `frontend/src/features/eda/queries.ts`, and `queries.test.tsx`; create `frontend/src/pages/EdaPage.test.tsx`, `frontend/src/features/eda/EdaFilters.tsx`, `CoveragePanel.tsx`, `MissingnessPanel.tsx`, `DistributionPanel.tsx`, `TemporalPatternsPanel.tsx`, `CorrelationPanel.tsx`, `SensorComparisonPanel.tsx`, and `CandidateOutliersPanel.tsx`.

**Interfaces:**

```ts
export interface EdaFiltersValue extends UrlFilters { sampleSize: number; xField: 'temperature_c' | 'relative_humidity_pct' | 'score'; yField: 'temperature_c' | 'relative_humidity_pct' | 'score' }
export interface EdaFiltersProps { value: EdaFiltersValue; onChange: (patch: Partial<EdaFiltersValue>) => void }
```

`sampleSize`, distribution bins, and scatter fields are local state because the approved canonical URL keys are limited to five. They remain bounded: bins 5 through 100 and max points 100 through 5,000. `xField !== yField`.

- [ ] Create red tests for restored URL filters, bounded local sample controls, quality/coverage, missingness, distributions, temporal patterns, correlation/scatter, six-sensor comparison, candidate outliers, absent sample versus null-field label, returned count text, independent errors, and absence of file input/upload/notebook/telemetry mutation/alert creation.
- [ ] Assert DOM contracts: heading `EDA`; controls `Sensor`, `From`, `To`, `Bucket`, `Sample size`, `X field`, and `Y field`; headings `Quality and coverage`, `Missingness`, `Distributions`, `Temporal patterns`, `Correlation and scatter`, `Sensor comparison`, and `Candidate outliers`.
- [ ] Run `npm test -- src/pages/EdaPage.test.tsx src/features/eda/queries.test.tsx`; expect missing page/panel failures.

```tsx
// frontend/src/pages/EdaPage.tsx
import { Stack, Typography } from '@mui/material'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { EmptyState } from '../components/states/EmptyState'
import { ApiErrorPanel } from '../components/states/ApiErrorPanel'
import { PanelSkeleton } from '../components/states/PanelSkeleton'
import { parseUrlFilters, updateUrlFilters } from '../features/filters/urlFilters'
import { useEdaCorrelationQuery, useEdaSummaryQuery } from '../features/eda/queries'
import { EdaFilters } from '../features/eda/EdaFilters'
import { CoveragePanel } from '../features/eda/CoveragePanel'
import { MissingnessPanel } from '../features/eda/MissingnessPanel'
import { DistributionPanel } from '../features/eda/DistributionPanel'
import { TemporalPatternsPanel } from '../features/eda/TemporalPatternsPanel'
import { CorrelationPanel } from '../features/eda/CorrelationPanel'
import { SensorComparisonPanel } from '../features/eda/SensorComparisonPanel'
import { CandidateOutliersPanel } from '../features/eda/CandidateOutliersPanel'
export function EdaPage() {
  const [params, setParams] = useSearchParams()
  const [sampleSize, setSampleSize] = useState(1_000)
  const filters = parseUrlFilters(params)
  const summary = useEdaSummaryQuery(filters)
  const correlation = useEdaCorrelationQuery({ deviceId: filters.sensor, from: filters.from, to: filters.to, xField: 'temperature_c', yField: 'relative_humidity_pct', maxPoints: sampleSize })
  return <Stack spacing={3}><Typography variant="h1">EDA</Typography><EdaFilters value={{ ...filters, sampleSize, xField: 'temperature_c', yField: 'relative_humidity_pct' }} onChange={(patch) => { if (patch.sampleSize !== undefined) setSampleSize(patch.sampleSize); setParams(updateUrlFilters(params, { sensor: patch.sensor, from: patch.from, to: patch.to, bucket: patch.bucket })) }} />{summary.data ? summary.data.coverage.observed_count === 0 ? <EmptyState title="No EDA records returned" detail="Adjust the selected time range or sensor scope." /> : <CoveragePanel coverage={summary.data.coverage} /> : summary.isError ? <ApiErrorPanel error={summary.error} onRetry={() => void summary.refetch()} /> : <PanelSkeleton label="Loading EDA summary" />}<MissingnessPanel missingness={summary.data?.missingness ?? []} /><DistributionPanel filters={filters} /><TemporalPatternsPanel filters={filters} /><CorrelationPanel response={correlation.data} /><SensorComparisonPanel rows={summary.data?.sensor_comparison ?? []} /><CandidateOutliersPanel rows={summary.data?.candidate_outliers ?? []} /></Stack>
}
```

```tsx
// frontend/src/features/eda/CandidateOutliersPanel.tsx
import { Typography } from '@mui/material'
import type { CandidateOutlier } from '../../contracts/eda'
export function CandidateOutliersPanel({ rows }: { rows: readonly CandidateOutlier[] }) {
  return <section aria-labelledby="candidate-outliers"><Typography id="candidate-outliers" variant="h2">Candidate outliers</Typography><Typography>Exploratory candidates, not alert state.</Typography>{rows.map(row => <Typography key={`${row.device_id}-${row.start_ts}`}>{row.device_id}: {row.reason}, score {row.score}</Typography>)}</section>
}
```

- [ ] Run `npm test -- src/pages/EdaPage.test.tsx src/features/eda/queries.test.tsx src/components/charts/options.test.ts`; expect pass.

**Acceptance:** seven named panels exist and use bounded responses; temporal panels reuse history/inference endpoints; candidate outliers are never alert state; filters survive empty/error state; no file upload appears.

## Task 11: Model Evaluation

**Depends on:** Tasks 3, 4, 5, 6. **Consumes:** evaluation hooks, `model_version`, ECharts evaluation builders, shared state. **Produces:** versioned artifact inspection with conditional labeled metrics.

**Files:** Modify `frontend/src/pages/ModelEvaluationPage.tsx`, `frontend/src/features/modelEvaluation/queries.ts`, and `queries.test.tsx`; create `frontend/src/pages/ModelEvaluationPage.test.tsx`, `frontend/src/features/modelEvaluation/VersionSelect.tsx`, `MetricsPanel.tsx`, and `LabeledMetricsPanels.tsx`.

**Interfaces:**

```ts
export interface VersionSelectProps { versions: readonly ModelEvaluationSummary[]; value?: string; onChange: (version: string) => void }
export interface MetricsPanelProps { availableMetrics: readonly string[]; metrics: Record<string, number> }
export interface LabeledMetricsPanelsProps { artifact: ModelEvaluationDetail }
```

- [ ] Create red tests for list empty/error state, `model_version` restoration and invalid normalization, only-declared metric rendering, missing labeled panels for unlabeled artifacts, labeled panels only when declaration and matching data both exist, and detail refetch without background polling after version change.
- [ ] Assert DOM contracts: heading `Model Evaluation`; combobox `Model version`; heading `Artifact metrics`; chart labels `Confusion matrix`, `ROC curve`, and `Precision recall curve` only for a labeled artifact with declared data.
- [ ] Run `npm test -- src/pages/ModelEvaluationPage.test.tsx`; expect missing components.

```tsx
// frontend/src/features/modelEvaluation/MetricsPanel.tsx
import { Typography } from '@mui/material'
export interface MetricsPanelProps { availableMetrics: readonly string[]; metrics: Record<string, number> }
export function MetricsPanel({ availableMetrics, metrics }: MetricsPanelProps) {
  return <section aria-labelledby="artifact-metrics"><Typography id="artifact-metrics" variant="h2">Artifact metrics</Typography>{availableMetrics.map(name => <Typography key={name}>{name}: {metrics[name]}</Typography>)}</section>
}

// frontend/src/features/modelEvaluation/LabeledMetricsPanels.tsx
import { Stack } from '@mui/material'
import { EChart } from '../../components/charts/EChart'
import { buildConfusionMatrixOptions, buildPrecisionRecallOptions, buildRocOptions } from '../../components/charts/evaluationOptions'
import type { ModelEvaluationDetail } from '../../contracts/modelEvaluation'
export interface LabeledMetricsPanelsProps { artifact: ModelEvaluationDetail }
export function LabeledMetricsPanels({ artifact }: LabeledMetricsPanelsProps) {
  if (!artifact.has_labeled_ground_truth) return null
  return <Stack spacing={2}>{artifact.confusion_matrix && artifact.available_metrics.includes('confusion_matrix') ? <EChart option={buildConfusionMatrixOptions(artifact.confusion_matrix)} ariaLabel="Confusion matrix" height={320} /> : null}{artifact.roc && artifact.available_metrics.includes('roc') ? <EChart option={buildRocOptions(artifact.roc)} ariaLabel="ROC curve" height={320} /> : null}{artifact.precision_recall && artifact.available_metrics.includes('precision_recall') ? <EChart option={buildPrecisionRecallOptions(artifact.precision_recall)} ariaLabel="Precision recall curve" height={320} /> : null}</Stack>
}
```

```tsx
// frontend/src/pages/ModelEvaluationPage.tsx
import { Stack, Typography } from '@mui/material'
import { useSearchParams } from 'react-router-dom'
import { EmptyState } from '../components/states/EmptyState'
import { ApiErrorPanel } from '../components/states/ApiErrorPanel'
import { PanelSkeleton } from '../components/states/PanelSkeleton'
import { updateUrlFilters } from '../features/filters/urlFilters'
import { useModelEvaluationQuery, useModelEvaluationsQuery } from '../features/modelEvaluation/queries'
import { VersionSelect } from '../features/modelEvaluation/VersionSelect'
import { MetricsPanel } from '../features/modelEvaluation/MetricsPanel'
import { LabeledMetricsPanels } from '../features/modelEvaluation/LabeledMetricsPanels'
export function ModelEvaluationPage() {
  const [params, setParams] = useSearchParams()
  const listing = useModelEvaluationsQuery()
  const selected = params.get('model_version') ?? listing.data?.items[0]?.version
  const detail = useModelEvaluationQuery(selected)
  if (listing.isLoading) return <PanelSkeleton label="Loading evaluation artifacts" />
  if (!listing.data?.items.length) return <EmptyState title="No evaluation artifact exists" detail="Live scores do not establish model quality." />
  return <Stack spacing={3}><Typography variant="h1">Model Evaluation</Typography><VersionSelect versions={listing.data.items} value={selected} onChange={(modelVersion) => setParams(updateUrlFilters(params, { modelVersion }))} />{detail.data ? <><Typography>Evaluation period: {detail.data.evaluation_period}</Typography><Typography>Model hash: {detail.data.model_hash}</Typography><MetricsPanel availableMetrics={detail.data.available_metrics} metrics={detail.data.metrics} /><LabeledMetricsPanels artifact={detail.data} /></> : detail.isError ? <ApiErrorPanel error={detail.error} onRetry={() => void detail.refetch()} /> : <PanelSkeleton label="Loading selected evaluation artifact" />}</Stack>
}
```

- [ ] Run `npm test -- src/pages/ModelEvaluationPage.test.tsx src/components/charts/options.test.ts`; expect pass.

**Acceptance:** selected version persists; hashes/evaluation scope render when provided; no metric or classification panel is invented; an empty artifact state makes no quality conclusion.

## Task 12: System Health

**Depends on:** Tasks 3, 4, 5. **Consumes:** `useSystemStatusQuery`, `SensorStatus`, poll-failure notice. **Produces:** a 30-second status snapshot that keeps the four health meanings distinct.

**Files:** Modify `frontend/src/pages/SystemHealthPage.tsx`, `frontend/src/features/systemHealth/query.ts`, and `query.test.tsx`; create `frontend/src/pages/SystemHealthPage.test.tsx`, `frontend/src/features/systemHealth/StatusSnapshot.tsx`, and `ServiceStatusTable.tsx`.

**Interfaces:**

```ts
export interface StatusSnapshotProps { snapshot: SystemStatusResponse; displayedAt: string }
export interface ServiceStatusTableProps { services: readonly SystemServiceStatus[] }
```

- [ ] Create red tests for separate service liveness/readiness text, telemetry timestamp/age and counts, 30-second polling, failed-refetch snapshot preservation, current-reachability unknown notice, poll age distinct from telemetry age, retry, and no aggregate green health badge.
- [ ] Assert DOM contracts: heading `System Health`; region heading `Latest known system snapshot`; table caption `Service liveness and readiness`; text labels `Snapshot checked at`, `Telemetry latest timestamp`, `Telemetry age`, `Liveness`, and `Readiness`.
- [ ] Run `npm test -- src/pages/SystemHealthPage.test.tsx src/features/systemHealth/query.test.tsx`; expect missing exports.

```tsx
// frontend/src/features/systemHealth/StatusSnapshot.tsx
import { Typography } from '@mui/material'
import type { SystemStatusResponse } from '../../contracts/systemHealth'
export interface StatusSnapshotProps { snapshot: SystemStatusResponse; displayedAt: string }
export function StatusSnapshot({ snapshot, displayedAt }: StatusSnapshotProps) {
  return <section aria-labelledby="status-snapshot"><Typography id="status-snapshot" variant="h2">Latest known system snapshot</Typography><Typography>Snapshot checked at: {snapshot.checked_at}</Typography><Typography>Displayed at: {displayedAt}</Typography><Typography>Telemetry latest timestamp: {snapshot.telemetry.latest_ts ?? 'Unavailable'}</Typography><Typography>Telemetry age: {snapshot.telemetry.age_seconds ?? 'Unknown'} seconds</Typography><Typography>Fresh sensors: {snapshot.telemetry.fresh_sensor_count}; stale sensors: {snapshot.telemetry.stale_sensor_count}; offline sensors: {snapshot.telemetry.offline_sensor_count}</Typography></section>
}

// frontend/src/features/systemHealth/ServiceStatusTable.tsx
import type { SystemServiceStatus } from '../../contracts/systemHealth'
export interface ServiceStatusTableProps { services: readonly SystemServiceStatus[] }
export function ServiceStatusTable({ services }: ServiceStatusTableProps) {
  return <table><caption>Service liveness and readiness</caption><thead><tr><th>Service</th><th>Liveness</th><th>Readiness</th><th>Checked at</th><th>Detail</th></tr></thead><tbody>{services.map(service => <tr key={service.name}><th scope="row">{service.name}</th><td>{service.liveness}</td><td>{service.readiness}</td><td>{service.checked_at}</td><td>{service.detail}</td></tr>)}</tbody></table>
}
```

- [ ] Run `npm test -- src/pages/SystemHealthPage.test.tsx src/features/systemHealth/query.test.tsx`; expect pass.

**Acceptance:** liveness, readiness, telemetry freshness, and status-poll freshness remain separately named. Failed polling retains the snapshot, marks current reachability unknown, and offers retry.

## Task 13: Playwright and visuals

**Depends on:** Tasks 7 through 12. **Consumes:** complete browser SPA and development MSW worker. **Produces:** operator flows, keyboard evidence, six 1440px screenshot baselines, and overflow/clipping checks at all three desktop widths.

**Files:** Create `frontend/playwright.config.ts`, every `frontend/tests/e2e/*` file, and only six `frontend/tests/e2e/visual.spec.ts-snapshots/*.png` baselines through Playwright.

**Interfaces:**

```ts
export type DesktopProject = 'desktop-1280' | 'desktop-1440' | 'desktop-1920'
export function scenarioUrl(route: string, scenario: MockScenario): string {
  const url = new URL(route, 'http://127.0.0.1:5173')
  url.searchParams.set('__scenario', scenario)
  return `${url.pathname}?${url.searchParams}`
}
```

- [ ] Install the browser with `npx playwright install chromium`; expect a successful Chromium download.
- [ ] Run `npm run test:e2e -- --project=desktop-1440`; expect configuration or test-discovery failure before `playwright.config.ts` and the browser-flow files exist.
- [ ] Create three Chromium projects, all height 900, widths 1280, 1440, and 1920. Do not create a mobile project.

```ts
// frontend/playwright.config.ts
import { defineConfig, devices } from '@playwright/test'
export default defineConfig({ testDir: './tests/e2e', webServer: { command: 'npm run dev -- --host 127.0.0.1', url: 'http://127.0.0.1:5173', reuseExistingServer: !process.env.CI }, projects: [1280, 1440, 1920].map(width => ({ name: `desktop-${width}`, use: { ...devices['Desktop Chrome'], viewport: { width, height: 900 } } })) })
```

- [ ] Create browser flows that use DOM roles and labels only: Overview triage, Sensor Detail filter/gap/retry/`Lihat data`, acknowledge then resolve, active direct resolve using in-page `fetch` and 409 confirmation, EDA filter/sample, model-version conditional panels, System Health failed poll, and visible focus through navigation/filters/grid/actions/dialog.
- [ ] Run the named operator flows only in `desktop-1440`; expect all non-visual flows to pass.
- [ ] Run one lightweight layout spec for all six routes in all three desktop projects; assert document width equals client width and no interactive control is clipped.

```ts
// frontend/tests/e2e/visual.spec.ts
import { expect, test } from '@playwright/test'
import { scenarioUrl } from './helpers'

for (const route of ['/', '/sensors/n4', '/alerts', '/eda', '/model-evaluation', '/system-health']) {
  test(`${route} active anomaly visual`, async ({ page }) => {
    await page.goto(scenarioUrl(route, 'active-anomaly'))
    await expect(page.getByRole('heading')).toBeVisible()
    await expect(page).toHaveScreenshot(`${route === '/' ? 'overview' : route.slice(1).replaceAll('/', '-')}.png`, { fullPage: true, animations: 'disabled' })
  })
}
```

- [ ] Generate baselines with `npm run test:e2e -- tests/e2e/visual.spec.ts --project=desktop-1440 --update-snapshots`; expect exactly 6 `.png` files, one per route.
- [ ] Run `npm run test:e2e -- tests/e2e/visual.spec.ts --project=desktop-1440`; expect exactly 6 screenshot comparisons to pass.

**Acceptance:** all flows use the browser MSW worker, not Playwright API request context; no unhandled request or console error occurs; all six routes pass layout checks at all three desktop widths; exactly six 1440px baselines exist; no 1280px, 1920px, or mobile baseline exists.

## Task 14: Production Docker and Nginx

**Depends on:** Task 3 and Tasks 7 through 12. **Consumes:** completed SPA build and development-only mock boundary. **Produces:** static production image, SPA deep-link fallback, future API proxy locations, artifact smoke proof, and no MSW in image/dist.

**Files:** Create `frontend/Dockerfile`, `frontend/nginx.conf`, `frontend/.dockerignore`, `frontend/tests/production/verify-dist.test.mjs`. Modify `frontend/package.json`, `frontend/vite.config.ts`, or `frontend/src/main.tsx` only where Task 3’s exclusion boundary needs it.

**Wave 2 shared-config rule:** Task 13 exclusively owns `playwright.config.ts` and `tests/e2e/**`; Task 14 exclusively owns production/container files. `package.json`, `package-lock.json`, `vite.config.ts`, and `src/main.tsx` stay read-only unless Task 14's red production test proves one minimal correction is required. Task 14 is then the sole writer and Task 13 reruns the command that read the shared configuration.

**Interfaces:**

```ts
export type DeferredProxyPath = '/api/' | '/health' | '/ready'
export interface ProductionArtifactReport { files: readonly string[]; hasMswWorker: false; hasScenarioData: false; usesRelativeApiPaths: true }
export declare function verifyProductionArtifact(distDirectory: URL): Promise<ProductionArtifactReport>
```

**Consumes:** the Task 3 production exclusion boundary and the complete frontend build. **Produces:** the static image, SPA fallback, `DeferredProxyPath` locations, and a passing `ProductionArtifactReport`. Production serves `/` and SPA fallback immediately. It prepares but does not require later FastAPI proxy targets for `/api/`, `/health`, and `/ready`. Container health checks static root content, never a proxied backend path.

- [ ] Create the red artifact verifier. Run `npm run test:production`; expect failure before the verifier and production exclusions exist.

```js
// frontend/tests/production/verify-dist.test.mjs
import assert from 'node:assert/strict'
import { readFile, readdir } from 'node:fs/promises'
import { test } from 'node:test'
import { join } from 'node:path'

async function files(root) { const entries = await readdir(root, { withFileTypes: true }); return (await Promise.all(entries.map(async entry => entry.isDirectory() ? files(join(root, entry.name)) : [join(root, entry.name)]))).flat() }
test('production artifacts exclude MSW and retain relative API paths', async () => {
  const dist = await files(new URL('../../dist/', import.meta.url))
  const text = (await Promise.all(dist.map(file => readFile(file, 'utf8').catch(() => '')))).join('\n')
  assert.equal(text.includes('mockServiceWorker'), false)
  assert.equal(text.includes('active-anomaly'), false)
  assert.equal(text.includes('alert_n4_active'), false)
  assert.match(text, /\/api\/telemetry\/latest/)
  assert.equal(/https?:\/\/[^\s"']+\/api\//.test(text), false)
})
```

- [ ] Create the multi-stage Dockerfile and Nginx configuration. The Nginx resolver defers DNS resolution until requests reach future backend routes, so the frontend begins serving without an `api` service.

```dockerfile
# frontend/Dockerfile
FROM node:22.12-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD wget -qO- http://127.0.0.1/ | grep -q '<div id="root"></div>' || exit 1
```

```nginx
# frontend/nginx.conf
server {
  listen 80;
  server_name _;
  root /usr/share/nginx/html;
  resolver 127.0.0.11 valid=10s ipv6=off;
  location / { try_files $uri $uri/ /index.html; }
  location /api/ { set $api_upstream http://api:8000; proxy_pass $api_upstream; proxy_set_header Host $host; }
  location = /health { set $api_upstream http://api:8000; proxy_pass $api_upstream; proxy_set_header Host $host; }
  location = /ready { set $api_upstream http://api:8000; proxy_pass $api_upstream; proxy_set_header Host $host; }
}
```

- [ ] Run `npm run build && npm run test:production`; expect both to pass.
- [ ] Run `docker build -t anomaly-frontend:local .`; expect successful image construction.
- [ ] Run `docker run --rm -d --name anomaly-frontend -p 127.0.0.1:8080:80 anomaly-frontend:local`; expect a running container even though no API exists.
- [ ] Run `curl -fsSI http://127.0.0.1:8080/alerts && curl -fsSI http://127.0.0.1:8080/sensors/n4`; expect HTTP 200 and SPA HTML fallback for both routes.
- [ ] Run `docker exec anomaly-frontend nginx -t`; expect successful syntax validation.
- [ ] Run `docker exec anomaly-frontend find /usr/share/nginx/html -iname '*msw*' -o -iname '*mockServiceWorker*'`; expect no output and exit 0.
- [ ] Run `docker stop anomaly-frontend`; expect a stopped container.

**Acceptance:** image serves independently without API; deep links work; `/api/`, `/health`, `/ready` have deferred DNS-safe future proxy rules; image health check is static-root based; dist/image have no MSW worker, handler, fixture, or scenario data; no Compose/backend container exists.

## Task 15: Acceptance gate

**Depends on:** Tasks 13 and 14. **Consumes:** all completed code and evidence. **Produces:** pass/fail decision only. No new product code or documentation belongs here.

**Files:** No new file. Correct a prior task only when its automated evidence proves a requirement is missing.

**Interfaces:**

```ts
export type AcceptanceCommand = 'npm ci' | 'npm run lint' | 'npm test' | 'npm run build' | 'npm run test:production' | 'npm run test:e2e'
export interface AcceptanceEvidence { command: AcceptanceCommand; exitCode: 0; summary: string }
```

**Consumes:** all prior task outputs and their tests. **Produces:** `readonly AcceptanceEvidence[]` covering the exact routes, URL keys, lifecycle, endpoint behaviors, chart properties, named scenarios, visual baselines, and production exclusion described above.

- [ ] Before beginning this gate on an incomplete predecessor state, run `npm run test:production && npm run test:e2e`; expect failure because the artifact verifier, browser flows, or six generated baselines are absent. Start this task only after Tasks 13 and 14 turn those failures green.
- [ ] Run `npm ci`; expect lockfile-consistent installation and exit 0.
- [ ] Run `npm run lint`; expect zero errors.
- [ ] Run `npm test`; expect zero failed contract, adapter, mock, hook, component, chart, and page tests.
- [ ] Run `npm run build`; expect successful `dist/` creation.
- [ ] Run `npm run test:production`; expect exclusion checks to pass.
- [ ] Run `npm run test:e2e`; expect every operator flow, all desktop layout checks, and exactly 6 visual comparisons to pass.
- [ ] Repeat Task 14’s build/container/deep-link/Nginx smoke commands; expect exit 0 and HTTP 200 deep links.
- [ ] Reject completion if a test is skipped, focused, updated in place, absent, or failing.
- [ ] After all commands pass, run one final code review for Tasks 8–15. Do not launch separate per-task Oracle, Review Work, visual-review, or report pipelines.

**Acceptance:** all ten approved criteria map to automated evidence below. Exactly six routes and six sensors remain. Production contains no MSW. No deferred backend work leaks into `frontend/`.

## Spec-to-task traceability

| Approved acceptance criterion | Primary tasks | Required automated evidence |
|---|---|---|
| 1. Exactly six SPA routes | 1, 7 through 12, 13, 15 | `routes.test.tsx`; six route Playwright checks |
| 2. URL filters persist and restore | 4, 8 through 11, 15 | URL parser/hook tests; page restoration tests |
| 3. Loading, empty, stale/offline, poll failure, schema/API error, partial failure | 2, 4, 5, 7, 8, 10, 12, 15 | adapter, shared-state, hook, and page tests |
| 4. Three-lane time charts and required behaviors | 6, 8, 10, 13, 15 | pure option tests; Sensor Detail and EDA browser checks |
| 5. Alert lifecycle and exact retry body | 3, 4, 9, 13, 15 | MSW lifecycle tests; hook identity tests; page/browser lifecycle flow |
| 6. Seven bounded EDA panels without CSV | 2, 4, 6, 10, 13, 15 | EDA hook/page tests; browser filter/sample flow |
| 7. Versioned evaluation and labeled-only panels | 2, 4, 6, 11, 13, 15 | contract and page tests; model-version browser flow |
| 8. Four distinct System Health meanings | 2, 4, 5, 12, 13, 15 | status hook/page tests; failed-poll browser flow |
| 9. Chart accessibility and `Lihat data` | 5, 6, 8, 10, 13, 15 | component/chart/page/keyboard tests |
| 10. Nginx production SPA, relative API, dev/test MSW only | 2, 3, 13, 14, 15 | adapter tests; dist verifier; Docker deep-link smoke |

## Conditional atomic commit strategy

This workspace is not a Git repository. Do not initialize Git, stage files, commit, or run Git commands. If the user later initializes Git and explicitly requests commits, use one docs-only commit for this workflow revision; one atomic commit for each of Tasks 8–12; separate commits for Tasks 13 and 14; and no Task 15 commit unless acceptance exposes a correction.

## Plan self-review checklist

- [x] Completion-marker scan: no unresolved task marker or vague task step appears in the plan.
- [x] Type/signature consistency: every task consumes exports from its declared dependency tasks; lifecycle body creation is confined to `createAlertLifecycleCommand`.
- [x] Path consistency: every path is under `frontend/`; app code is constrained to `src/app`, `src/pages`, `src/features`, `src/components`, `src/api`, `src/contracts`, `src/mocks`, and `src/theme`.
- [x] Spec coverage: all six pages, six sensors, endpoint bounds, response validation, scenarios, lifecycle, poll intervals, 8-second timeout, accessibility, desktop widths, and production exclusion are explicit.
- [x] Dependency ordering: completed Tasks 1–7 precede parallel Tasks 8–12; parallel Tasks 13–14 follow Wave 1 with one shared-config writer; Task 15 follows both.
- [x] Command validity: setup, red/green tests, build, generated-worker, Playwright, artifact, Docker, curl, Nginx, and cleanup commands use the future `frontend/` working directory where required.

## Execution handoff

**Parallel execution, required:** Update this plan first. Then execute Tasks 8–12 concurrently with one worker per task and strict file ownership. Wait for all five targeted test and changed-file diagnostic gates before starting Tasks 13 and 14 concurrently. After both pass, execute Task 15 sequentially.

Do not add another design cycle, nested subagents, per-task Oracle or Review Work passes, per-task browser/visual checks, full-suite repetitions, pixel diffs, or report artifacts.

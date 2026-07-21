# Frontend-First Design Authority: Web IoT Anomaly Detection Platform

> **Created:** 19 Jul 2026  
> **Status:** Approved in design review; awaiting written-spec review  
> **Scope:** Complete desktop React SPA with a mock API contract before backend, MQTT, database, and ML implementation

## 1. Authority, Scope, and Sequencing

The master system specification at `docs/superpowers/specs/2026-07-15-web-iot-anomaly-detection-design.md` remains authoritative for the whole platform. This document owns frontend scope, interaction rules, UI sequencing, frontend contracts, and frontend test evidence. Where frontend detail differs from older wording in the master specification, this document is the authority for the frontend only.

The old Laravel, Redis, ClickHouse, and ONNX implementation plan at `docs/superpowers/plans/2026-07-15-web-iot-anomaly-detection.md` remains obsolete. It is not an implementation guide and must not be revived.

Implementation proceeds frontend first:

1. Build and test the complete React SPA against deterministic MSW contracts.
2. Confirm all six routes, UI states, charts, lifecycle actions, accessibility alternatives, and desktop visual checks.
3. Implement FastAPI to satisfy the same typed `/api` contracts.
4. Implement TimescaleDB persistence, MQTT ingestion, and ML inference after the frontend contract is stable.
5. Replace MSW only in development and test transport with FastAPI. Page, hook, adapter, and contract interfaces remain unchanged.

The initial deliverable is a complete React SPA with a mock API, a frontend Docker image, and Nginx production-serving configuration, not a static mockup. The approved action-first Overview direction in `.superpowers/brainstorm/914937-1784384419/content/action-first-dashboard-v4.html` is the visual and interaction reference. It is not edited by this work.

## 2. Product Boundary

The application is desktop only. The baseline viewport is 1440 by 900 CSS pixels. Visual and interaction checks also run at 1280 and 1920 pixel desktop widths. Mobile layouts, touch-specific interactions, and responsive mobile navigation are excluded.

The domain contains exactly six sensors, `n1` through `n6`. Every sensor selector, overview summary, mock scenario, comparison control, and test fixture uses that closed set.

The application has exactly six pages.

| Group | Page | Route | Approved responsibility |
|---|---|---|---|
| Operations | Overview | `/` | Action-first triage for all six sensors. Show freshness, current temperature, RH, score, active-alert count, and the next operator action. Surface current active alerts and link directly to the affected sensor or alert. Do not turn the page into a dense analytics report. |
| Operations | Sensor Detail & History | `/sensors/:sensorId` | Investigate one selected sensor with telemetry and inference history, alert context, filters, aligned charts, and a tabular `Lihat data` alternative. |
| Operations | Alerts | `/alerts` | Review current and historical alerts in a filterable grid, inspect immutable event history, acknowledge active alerts, and resolve acknowledged alerts only. |
| Analysis | EDA | `/eda` | Directly explore telemetry quality and patterns for thesis examiners. It is interactive product UI, not CSV upload, a notebook, or a BI clone. |
| Analysis | Model Evaluation | `/model-evaluation` | Inspect versioned evaluation artifacts and only the metrics available for the selected version. |
| System | System Health | `/system-health` | Show the latest known system-status snapshot, service liveness and readiness meaning, telemetry freshness, and stale or failed status polling. |

There are no extra pages for authentication, file upload, notebooks, dashboards, or configuration.

## 3. Final Frontend Stack and Project Layout

| Area | Final choice | Decision |
|---|---|---|
| SPA | React, Vite, TypeScript | Required application foundation. |
| UI | MUI Core | Layout, forms, navigation, accessibility primitives, and tokens. |
| Tables | MUI X Data Grid Community | Alert and data grids without commercial features. |
| Charts | Apache ECharts | Time interaction and chart composition. It replaces MUI X Charts. |
| Chart theming | ECharts options derived from MUI theme tokens | One visual system for UI and charts. |
| Routing | React Router | Six-page client routes and URL search parameters. |
| Server state | TanStack Query | Fetching, caching, polling, invalidation, and mutation states. |
| Contract mocking | MSW, development and test only | The same relative `/api` calls used by FastAPI later. |
| Unit and component tests | Vitest and React Testing Library | Contract, state, and accessible UI evidence. |
| Browser tests | Playwright | Desktop operator flows and visual regression evidence. |
| Production serving | Frontend Docker image and Nginx | Part of the frontend-first deliverable. Serve the built SPA now, proxy application data endpoints at relative `/api` to FastAPI later, and include root `/health` and `/ready` proxy rules as explicit exceptions. |

Redux is not used. TanStack Query owns server state, while local component state and URL search parameters own local and navigable UI state.

The project root is `frontend/`. Application modules live only under:

```text
frontend/
  src/
    app/
    pages/
    features/
    components/
    api/
    contracts/
    mocks/
    theme/
```

Vite configuration, TypeScript configuration, public assets, test configuration, Playwright configuration, Dockerfile, and Nginx files remain under `frontend/` outside `src` where appropriate. This layout is a design rule, not permission to create those files during this documentation task.

## 4. Data Flow, Transport, and Polling

The frontend data path is fixed:

```text
Page -> feature hook -> typed API adapter -> relative /api request -> MSW now, FastAPI later
```

Pages do not call `fetch` directly. Feature hooks own query keys, polling cadence, selected parameters, stale presentation, and mutation state. Typed adapters own request construction, response validation, Problem Details conversion, and relative `/api` paths. Contracts define request and response shapes shared by adapters and MSW handlers.

Application data endpoints use relative `/api` requests. Root `/health` and `/ready` are explicit exceptions, not `/api` endpoints, and Nginx proxies all three paths to FastAPI when it is implemented. No frontend environment variable contains a backend host. MSW intercepts application data requests only in development and test. The production build excludes MSW initialization, worker setup, handlers, and mock data from its runtime path. The frontend Docker image and Nginx serve the production SPA in this deliverable; the proxy rules are ready for FastAPI later.

| Resource | Trigger | Interval | Failure behavior |
|---|---|---:|---|
| Latest telemetry | Initial page load and active polling | 10 seconds | Keep last known values, label them stale, and show polling failure without erasing the overview. |
| Current alerts | Initial page load and active polling | 10 seconds | Keep last known rows, label them stale, and preserve action history. |
| System status | Initial page load and active polling | 30 seconds | Keep last known status, show its age, and show that current reachability is unknown. |
| Telemetry and inference history | Sensor, time, or bucket change | No background polling | Fetch on parameter change only. |
| EDA | Filter or bounded-sample change | No background polling | Fetch on parameter change only. |
| Model evaluation | Version change | No background polling | Fetch on version change only. |

The selected sensor, time range, bucket, and model version persist in URL search parameters. Canonical names are `sensor`, `from`, `to`, `bucket`, and `model_version`. A sensor detail route uses `:sensorId` as the selected sensor and also updates `sensor` where a cross-page link needs a common filter. URL parameters are parsed, validated against supported values, and reflected in controls on load.

## 5. Page and Interaction Specification

### 5.1 Overview

The Overview preserves the approved action-first dashboard direction. It answers, in order: what needs attention, which sensor is affected, how recent the data is, and what an operator can do next.

The page presents all six sensors in a consistent card or compact-row treatment. Each item includes the sensor ID, temperature, RH, latest score when available, last telemetry timestamp, freshness state, and an accessible status label. Active anomalies receive visual priority and a clear link to the relevant alert or sensor history. Empty score data is not treated as a normal score. Stale data is not treated as offline. Current active alerts appear in an actionable list with acknowledgement available only for active alerts.

The Overview does not contain the full EDA surface, full evaluation report, raw telemetry grid, or a direct resolve control for an active alert.

### 5.2 Sensor Detail & History

This page starts from one of the six sensor IDs. It presents selected time and bucket controls, current freshness, historical telemetry, inference scores, related alert events, and a `Lihat data` control that exposes the same bounded records in an accessible table.

The chart area uses the ECharts conventions in section 6. The history panel tolerates missing values and gaps without joining them. A partial failure in the inference panel does not hide valid telemetry history, and a partial telemetry failure does not hide available alert context. Each failed panel shows its own retry control and request ID when supplied by the API.

### 5.3 Alerts

The Alerts page uses MUI X Data Grid Community for a filterable, keyboard-operable view of derived current alert state and immutable history access. Filters include sensor, status, and time range. The current-state grid is paginated. Selecting an alert opens or expands its event history without changing the lifecycle rules.

The only valid lifecycle is:

```text
detected -> acknowledged -> resolved
```

The UI labels derived `detected` state as **active**. An active alert can be acknowledged. Resolve is unavailable for active alerts and a direct resolve attempt is rejected. An acknowledged alert can be resolved. A resolved alert has no further lifecycle action.

Mutations are pessimistic. The UI does not move an alert between states until the server confirms the append. For one operator action, the frontend creates exactly one `command_id` and one timezone-aware `event_ts`, stores the exact body for the visible retry path, and sends that identical payload on every retry. A failed request keeps the original action available with the same command payload. A retry is never rebuilt with a new ID or timestamp.

### 5.4 EDA

EDA is a directly interactive exploration page aimed primarily at thesis examiners. It reads TimescaleDB telemetry through FastAPI later, using the contracts in section 7. It is not CSV upload and does not imitate a notebook or generic BI product.

Controls select a bounded sensor scope, time range, bucket, and requested sample size. The page exposes these focused panels:

1. **Quality and coverage:** expected versus observed readings, coverage percentage, freshness, and cadence gaps.
2. **Missingness:** missing or unavailable values by field and time range, including a visible distinction between absent samples and null fields.
3. **Distributions:** bounded histograms and summary statistics for temperature, RH, and available anomaly scores.
4. **Temporal patterns:** telemetry history through the reused temporal endpoints, including day or time bucket summaries where requested.
5. **Correlation and scatter:** temperature, RH, and score relationships from a bounded sample.
6. **Sensor comparison:** consistent selected-period summaries for the six sensors.
7. **Candidate outliers:** server-defined candidate points or intervals with their reason and score context. They are exploratory candidates, not operator alert state.

The page preserves the selected filters in the URL. It labels samples as bounded and shows the count returned. EDA never uploads a file, writes telemetry, or creates an alert.

### 5.5 Model Evaluation

Model Evaluation is separate from EDA. It is backed by versioned evaluation artifacts, not live exploratory samples. The page first lists available versions and then displays the selected version’s metadata, evaluation scope, artifact hashes where supplied, and only metrics actually available in that artifact.

Confusion matrix, ROC, and precision-recall panels render only when the selected artifact declares labeled ground truth and contains the matching data. The UI does not show empty or fabricated classification metrics for unlabeled telemetry. If no evaluation artifact exists, the page shows an explicit empty state and does not infer a model-quality conclusion from live scores.

### 5.6 System Health

System Health reads `/api/system/status` every 30 seconds. It distinguishes four meanings:

| Meaning | UI interpretation |
|---|---|
| Liveness | A process reported that it is running. Liveness is not proof that dependencies or artifacts are usable. |
| Readiness | A service reported that its required dependencies are usable for its assigned role. |
| Telemetry freshness | The age of the most recent reading. Fresh telemetry is not proof that every service is ready. |
| Status-poll freshness | The age of the displayed system snapshot. A failed poll leaves the last snapshot visible but marks current status unknown. |

The page must not collapse liveness, readiness, and data freshness into one green label.

## 6. ECharts and Visual Rules

ECharts is the only chart library. ECharts options derive color, typography, surface, divider, and text values from the active MUI theme tokens. The chart layer does not introduce an independent palette or gradient system.

Time-series views use three separate, vertically aligned lanes:

1. Temperature in degrees Celsius.
2. Relative humidity in percent.
3. Anomaly score.

The lanes share aligned x-time, linked crosshair or axis pointer behavior, and linked zoom. They use straight lines. Gaps remain gaps. Thresholds are dashed lines in the score lane. Anomalies use clearly labeled markers or intervals, including interval treatment where an event spans a window. The chart does not use a third Y-axis.

Use a stable accessible palette with MUI semantic tokens for normal, warning, error, text, and divider roles. Status is never communicated by color alone. Charts include textual series labels, visible legends where needed, and a concise text summary. `Lihat data` offers the same bounded result set in a table for screen reader users, keyboard users, export-free review, and cases where the chart cannot be interpreted.

The following are prohibited: gradients, smoothed curves, decorative point clutter, automatic interpolation across gaps, a third Y-axis, and data encodings that rely on color alone. Chart controls must have visible keyboard focus and accessible labels. ECharts ARIA descriptions are enabled and describe the selected sensor, time range, available gaps, threshold context, and anomaly markers.

## 7. API Contract Authority

All endpoints return JSON. All timestamps are RFC 3339 timestamps with an explicit UTC offset, normally `Z`. List endpoints return bounded results and pagination metadata. The frontend must not request or render unbounded telemetry, inference, event, distribution, or scatter data.

### 7.1 Shared conventions

| Item | Contract |
|---|---|
| Sensor IDs | `n1` through `n6`. Any other value is a validation error. |
| Time ranges | `from` and `to` are timezone-aware RFC 3339 timestamps. `from` is inclusive and `to` is exclusive. `from` must precede `to`. |
| Buckets | `raw`, `1m`, `5m`, `15m`, `1h`, and `1d`. `raw` is still bounded by `limit`. |
| Pagination | `limit` is a positive bounded integer. Cursor endpoints return `next_cursor` or `null`. Offset endpoints return `page`, `page_size`, and `total` only where a stable total is meaningful. |
| Freshness | `fresh`, `stale`, or `unknown`. It describes the age and recency assessment of the latest telemetry. |
| Availability | `online`, `offline`, or `unknown`. It describes whether the selected sensor is currently available. |
| Request correlation | Responses include `request_id`. Clients display it in schema and API error states. |
| Errors | Problem Details fields are `type`, `title`, `status`, `detail`, `instance`, `request_id`, and optional `errors` keyed by invalid field. |
| API schema error | A response that fails frontend contract validation is shown as a schema/API error, with request ID and retry control. It is not silently coerced. |

`freshness` and `availability` are independent. A sensor can be online with stale data, offline while retaining a last known timestamp and age, or unknown when current state cannot be determined. Unless an endpoint states another bound, `limit` accepts 1 through 500. `GET /api/telemetry/history` and `GET /api/inference-results` accept at most 5,000 raw points or 2,000 bucketed points per response. `GET /api/alert-events` accepts at most 200 events per response. `GET /api/alerts/current` accepts `page_size` from 1 through 100. `GET /api/model-evaluations` accepts `page_size` from 1 through 50. These limits are part of the frontend contract and are mirrored by MSW.

A representative Problem Details response is:

```json
{
  "type": "https://example.invalid/problems/invalid-time-range",
  "title": "Invalid time range",
  "status": 422,
  "detail": "from must be earlier than to",
  "instance": "/api/telemetry/history",
  "request_id": "req_01J...",
  "errors": {
    "from": ["must be earlier than to"]
  }
}
```

### 7.2 Existing master endpoints

| Endpoint | Query or body fields | Representative successful response fields |
|---|---|---|
| `GET /api/telemetry/latest` | Optional `device_id` | `request_id`, `generated_at`, `sensors[]` with `device_id`, `ts`, `temperature_c`, `relative_humidity_pct`, `freshness`, `age_seconds`, `availability`. |
| `GET /api/telemetry/history` | Required `device_id`, `from`, `to`; optional `bucket`, `limit`, `cursor` | `request_id`, `device_id`, `from`, `to`, `bucket`, `points[]` with `ts`, `temperature_c`, `relative_humidity_pct`, `sample_count`, `gap_before`; `next_cursor`, `returned_count`. |
| `GET /api/inference-results` | Required `device_id`, `from`, `to`; optional `bucket`, `limit`, `cursor`, `model_version` | `request_id`, `device_id`, `model_version`, `points[]` with `window_start_ts`, `window_end_ts`, `score`, `threshold`, `is_anomaly`, `model_version`, `model_hash`, `preprocessing_hash`, `threshold_hash`; `next_cursor`, `returned_count`. |
| `GET /api/alert-events` | Optional `alert_id`, `device_id`, `from`, `to`, `limit`, `cursor` | `request_id`, `events[]` with `event_id`, `alert_id`, `event_ts`, `event_type`, `device_id`, `actor`, `note`, `inference_result_window_start_ts`, `inference_result_window_end_ts`, `inference_model_version`; `next_cursor`, `returned_count`. |
| `GET /api/alerts/current` | Optional `device_id`, `status`, `page`, `page_size` | `request_id`, `generated_at`, `items[]` with `alert_id`, `device_id`, `status`, `detected_at`, `latest_event_ts`, `latest_event_id`, `score`, `threshold`, `model_version`, `can_acknowledge`, `can_resolve`; `page`, `page_size`, `total`. |
| `POST /api/alerts/{alert_id}/acknowledge` | JSON body `command_id`, `event_ts`, optional `note` | `request_id`, `alert_id`, `status: "acknowledged"`, `event` using the alert-event fields, `idempotent_replay`. |
| `POST /api/alerts/{alert_id}/resolve` | JSON body `command_id`, `event_ts`, optional `note` | `request_id`, `alert_id`, `status: "resolved"`, `event` using the alert-event fields, `idempotent_replay`. Resolve rejects active alerts with a 409 Problem Details response. |
| `GET /health` | None | `status: "alive"`, `request_id`, `checked_at`. This is API liveness only. |
| `GET /ready` | None | `status: "ready"` or `"not_ready"`, `request_id`, `checked_at`, `dependencies[]`. This is API readiness only. |

The lifecycle request body is always:

```json
{
  "command_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_ts": "2026-07-19T10:31:00Z",
  "note": "Checked on site"
}
```

`command_id` and `event_ts` are client generated once per action. The frontend retries the exact same body. The API maps `command_id` to the immutable alert event identity and returns the original successful event for an idempotent replay.

### 7.3 Approved additions

Temporal EDA reuses `GET /api/telemetry/history` and `GET /api/inference-results`; it does not add a second temporal endpoint.

| Endpoint | Query fields | Representative successful response fields |
|---|---|---|
| `GET /api/eda/summary` | Optional `device_id`, required `from`, `to`; optional `bucket` | `request_id`, `scope` with `device_ids`, `from`, `to`, `bucket`; `coverage` with `expected_count`, `observed_count`, `coverage_pct`, `gap_count`; `missingness[]` with `field`, `missing_count`, `missing_pct`; `sensor_comparison[]` with `device_id`, `sample_count`, `coverage_pct`, `temperature_c` with `mean`, `p05`, `p95`, and `relative_humidity_pct` with `mean`, `p05`, `p95`; `candidate_outliers[]` with `device_id`, `start_ts`, `end_ts`, `reason`, `score`. |
| `GET /api/eda/distributions` | Optional `device_id`, required `from`, `to`, `field`; optional `bins` from 5 to 100 | `request_id`, `field`, `sample_count`, `summary` with `min`, `max`, `mean`, `median`, `p05`, `p95`; `bins[]` with `start`, `end`, `count`. |
| `GET /api/eda/correlation` | Optional `device_id`, required `from`, `to`; optional `x_field`, `y_field`, `max_points` from 100 to 5000, `cursor` | `request_id`, `x_field`, `y_field`, `sample_count`, `correlation`, `points[]` with `ts`, `device_id`, `x`, `y`, optional `score`, `is_candidate_outlier`; `next_cursor`. |
| `GET /api/model-evaluations` | Optional `page`, `page_size` | `request_id`, `items[]` with `version`, `created_at`, `evaluation_period`, `has_labeled_ground_truth`, `available_metrics`, `summary`; `page`, `page_size`, `total`. |
| `GET /api/model-evaluations/{version}` | Path `version` | `request_id`, `version`, `created_at`, `evaluation_period`, `model_hash`, `preprocessing_hash`, `threshold_hash`, `has_labeled_ground_truth`, `available_metrics`, `metrics`, optional `confusion_matrix`, optional `roc`, optional `precision_recall`, `notes`. |
| `GET /api/system/status` | None | `request_id`, `checked_at`, `overall_observation`, `services[]` with `name`, `liveness`, `readiness`, `checked_at`, `detail`; `telemetry` with `latest_ts`, `age_seconds`, `fresh_sensor_count`, `stale_sensor_count`, `offline_sensor_count`; optional `diagnostics`. |

`field` for distributions is `temperature_c`, `relative_humidity_pct`, or `score` when score data exists. `x_field` and `y_field` use the same values and must differ. The server rejects unbounded `bins`, `max_points`, `limit`, and invalid field combinations with Problem Details.

`available_metrics` is an array of stable metric identifiers. `metrics` is a string-to-number map whose keys are identifiers declared in `available_metrics`, for example `{"mae": 0.12, "rmse": 0.18}`. Optional labeled-ground-truth structures are present only when `has_labeled_ground_truth` is `true` and their identifiers are declared in `available_metrics`: `confusion_matrix` is `{ "labels": ["normal", "anomaly"], "matrix": [[true_normal, false_positive], [false_negative, true_positive]] }`, with rows as actual labels and columns as predicted labels; `roc` is `{ "auc": 0.98, "points": [{ "fpr": 0.0, "tpr": 0.0 }] }`; and `precision_recall` is `{ "average_precision": 0.94, "points": [{ "recall": 0.0, "precision": 1.0 }] }`.

## 8. UI States and Error Handling

Every data panel distinguishes these states. A page may show different states at once across independent panels.

| State | Required UI behavior |
|---|---|
| Initial loading | Show a layout-matched skeleton. Do not show an empty state before the first response. |
| Empty | Explain that the selected scope has no returned records. Keep filters visible and offer a clear filter adjustment path. |
| Stale or offline data | Retain the last successful data, show its timestamp and stale state, and distinguish stale data from an offline sensor or unknown current connectivity. |
| Polling failure | Retain last known poll data, show that the refresh failed, identify the affected resource, and allow retry. |
| Schema or API error | Show a bounded error panel with the Problem Details title and detail, request ID when supplied, and retry. Do not render unvalidated data. |
| Partial panel failure | Keep unaffected panels visible. The failed panel alone contains its error, request ID, and retry action. |

Mutations use a separate pending and error state. The alert row remains in its prior confirmed state while acknowledgement or resolution is pending. Lifecycle conflict responses refresh the current alert row and explain the confirmed transition without manufacturing a local state.

## 9. Deterministic MSW Contract Scenarios

The written frontend API contract in section 7 and typed contract definitions are authoritative. MSW handlers are the deterministic initial implementation of those contracts for development and test. They use fixed IDs, values, timestamps, pagination cursors, and fixture order, and provide these named scenarios:

| Scenario | Required deterministic behavior |
|---|---|
| Normal | Six sensors provide fresh latest telemetry, bounded history, normal scores, no active alerts, available EDA samples, versioned evaluation artifacts, and ready system services. |
| Active anomaly | `n4` has a threshold breach, an active current alert, anomaly markers in the score lane, and an available acknowledge action. |
| Stale | A selected sensor returns a valid but old timestamp and stale freshness. Other panels remain available. |
| Offline | The selected latest-telemetry request succeeds with a valid response whose selected sensor has `availability: "offline"`, `freshness: "unknown"`, and its last timestamp and `age_seconds` where available. It is distinct from Stale because it reports unavailability rather than an online sensor with old data. |
| Data gap | Historical telemetry contains a documented missing interval with `gap_before` and no interpolated points. Charts preserve the gap. |
| Empty | The selected filter range returns valid empty lists and zero counts. |
| Timeout | A delayed response exceeds the configured client timeout or remains pending long enough to prove loading and retry treatment. |
| Server error | The endpoint returns a deterministic Problem Details response with a fixed `request_id`. |

Alert state is mutable within a single MSW test or browser session. The active-anomaly scenario starts with one active alert. An acknowledge request with a new valid command stores an immutable acknowledgement event and changes derived current status to acknowledged. Resolve rejects an active alert, succeeds only after acknowledgement, and a repeat of an accepted command returns the original result as an idempotent replay. Test setup resets mutable alert state before every test, so one test cannot influence another.

## 10. Testing and Deferred Work

| Layer | Required evidence |
|---|---|
| Vitest, React Testing Library, MSW | Typed adapter requests and Problem Details handling, URL parameter restoration, skeleton and empty states, stale versus offline distinction, polling failure preservation, partial-panel failure isolation, alert lifecycle controls, identical idempotent retry payloads, EDA filters, and conditional model-evaluation panels. |
| Pure ECharts option builders | Aligned three-lane layout, linked axes and zoom, straight lines, gaps, dashed thresholds, anomaly marker or interval data, no third Y-axis, MUI token mapping, ARIA text, and table alternative metadata. |
| Playwright desktop flows | Overview triage, sensor history interaction, alert acknowledge then resolve, direct-resolve rejection, EDA filter changes, model-version changes, health-state interpretation, and keyboard-visible controls. |
| Visual regression | Baseline screenshots at 1440 by 900 and desktop checks at 1280 and 1920 widths for all six routes and active-anomaly state. |
| Production frontend image smoke test | Build the frontend image, serve the built SPA through Nginx, confirm MSW is absent from the production runtime path, and confirm application data requests remain relative `/api`. |

Backend API implementation, full Docker Compose, MQTT integration, TimescaleDB integration, and inference tests are explicitly deferred until the frontend contract suite passes. They are not part of this frontend-first deliverable.

## 11. Approved Acceptance Criteria

1. The SPA exposes exactly six routes: Overview, Sensor Detail & History, Alerts, EDA, Model Evaluation, and System Health.
2. Sensor, time range, bucket, and model version filters persist in URL search parameters and restore the corresponding controls and requests on reload.
3. The UI distinguishes initial loading, empty, stale or offline, polling failure, schema or API error with request ID and retry, and partial panel failure.
4. Time-series charts use three aligned lanes with shared time interaction and zoom, straight lines, preserved gaps, dashed thresholds, anomaly markers or intervals, no point clutter, and no third Y-axis.
5. Alert actions enforce detected to acknowledged to resolved. Active alerts cannot resolve, mutations are pessimistic, and retries send the exact same `command_id` and `event_ts` payload.
6. EDA provides consistent quality and coverage, missingness, distributions, temporal patterns, correlation or scatter, sensor comparison, and candidate outliers from bounded API data without CSV upload.
7. Model Evaluation switches among versioned artifacts, displays only declared metrics, and shows confusion matrix, ROC, and precision-recall only when labeled ground truth is available.
8. System Health distinguishes process liveness, service readiness, telemetry freshness, and status-poll freshness rather than reducing them to one health color.
9. Every chart has ECharts ARIA or text summary support, visible status text, keyboard-accessible controls, and a `Lihat data` alternative for the same bounded records.
10. The frontend Docker image serves the production SPA through Nginx without MSW, application data requests use relative `/api`, and development and test use MSW against those same contracts.

## 12. Rejected Alternatives

| Rejected alternative | Reason |
|---|---|
| Static local fixtures | They cannot prove loading, failure, polling, mutation, pagination, or contract behavior in a complete SPA. |
| Standalone mock API container | It adds another runtime and drifts from frontend test contracts without improving the frontend-first deliverable. |
| MUI X Charts Community | Its zoom limits do not meet the approved linked time zoom and multi-lane analysis needs. |
| MUI X Pro | Commercial licensing is unnecessary for the approved scope. |
| Recharts or Nivo | ECharts already meets the time-series, linked interaction, annotation, and ARIA requirements without a second chart stack. |
| Redux | TanStack Query plus local state and URL parameters covers the approved state model. |
| Mobile scope | The approved deliverable is desktop-only and is verified at 1280, 1440, and 1920 desktop widths. |
| CSV upload | EDA examines persisted telemetry through FastAPI later, not user-provided files. |
| Combining EDA and Model Evaluation | Exploratory telemetry analysis and versioned evaluation artifacts answer different questions and require different evidence. |

# Milestone One: Backend Serving and Persistence Design

**Date:** 2026-07-21  
**Status:** approved design; implementation-ready

## Authority and scope

This document is the milestone-one backend authority. The live frontend contracts, adapters, mock handlers, and tests in `frontend/src/contracts/`, `frontend/src/api/`, `frontend/src/mocks/handlers.ts`, and their tests override stale backend documents where they differ. The approved platform design remains the architectural authority for FastAPI, TimescaleDB, migrations, and Nginx.

M1 delivers real same-origin HTTP serving and durable TimescaleDB persistence. It deliberately defers live MQTT ingestion and PyTorch inference: seed jobs provide deterministic telemetry, inference, model-evaluation, and alert data. `/api/system/status` must report inference as deferred, not running. This supersedes the obsolete Laravel, Redis, ClickHouse, MySQL, ONNX, and 90-day-TTL assumptions; none are part of M1.

### Goals

- Serve the existing frontend through Nginx and implement its 15 exact HTTP boundaries with strict Zod-compatible JSON.
- Persist telemetry, seeded inference artifacts, stable alert identities, immutable alert events, commands, and evaluation artifacts in TimescaleDB.
- Make alert lifecycle commands durable, serialized per alert, globally idempotent, and safe to retry.
- Provide deterministic, startup-relative seed data and operational health semantics.

### Non-goals

- MQTT broker/client, PyTorch model loading or execution, live inference, streaming, retention policies, TimescaleDB compression, caching, authentication, and new frontend work.
- Extra services, public routes, tables, or host-exposed ports.

## Architecture and topology

`browser -> Nginx -> FastAPI -> TimescaleDB`

- Nginx serves the built frontend, falls back to the SPA entrypoint, and proxies `/api/`, `/health`, and `/ready` to FastAPI. Each proxy location uses `proxy_pass http://api:8000` with no URI component and no trailing slash, so Nginx forwards the unparsed request URI without replacement or normalization. All browser calls remain relative, same-origin paths.
- The backend package owns validation, response serialization, EDA queries computed on demand, migration checks, seed code, and database transactions. The one-shot seed job invokes that seed code; the API runtime does not orchestrate seeding.
- TimescaleDB is the only durable store. Migration and seed jobs use the same private database network and exit after completion.
- Compose starts `db`, then one-shot `migrate`, then one-shot `seed`, then `api`, then `nginx`; API starts only after migration succeeds. Seed is idempotent and runs after migration. Only Nginx publishes a host port. API, database, migration, and seed are private-network services.
- M1 creates no retention policy and no compression policy.

## Persistence model

Use exactly these six tables. Only `telemetry` and `inference_results` are Timescale hypertables; all timestamps are `timestamptz`. The other four tables are ordinary relational tables so `event_id` and `command_id` can be globally unique without hypertable partition-key constraints.

| Table | Identity and durable fields | Rules |
| --- | --- | --- |
| `telemetry` | `(device_id, ts)`; temperature, relative humidity, payload hash | `device_id` is constrained to `n1`…`n6`. Unique identity plus same payload hash is a no-op; different content at the same identity is rejected and never overwrites history. |
| `inference_results` | `(device_id, window_end_ts, model_version)`; window start, score, threshold, anomaly flag, model/preprocessing/threshold hashes | Seeded artifacts only in M1. Windows satisfy `start < end`; every numeric output is finite. The seed includes the active demo model version. |
| `alerts` | stable `alert_id`; device, detected time, score, threshold, model version, and source inference window/hash provenance | One row is created with detection and never represents mutable lifecycle status. It is the row locked to serialize commands for that alert. |
| `alert_events` | globally unique immutable `event_id`; alert id, event timestamp/type, actor, nullable note | Append-only lifecycle ledger. The `detected -> acknowledged -> resolved` sequence is derived from these rows and joined to `alerts` for stable detection provenance. |
| `alert_commands` | global `command_id`; canonical alert id, action, event timestamp, exact nullable note, nullable accepted event id | One row reserves every accepted command identity and makes replay durable; it stores no HTTP response or request id. |
| `model_evaluations` | `version`; creation time, evaluation period, hashes, labeled-ground-truth flag, declared metrics, metrics/curve payloads, nullable notes | Stores the frontend's summary/detail artifact shapes; labeled structures appear only when ground truth is true and declared. |

`/api/alerts/current` is a projection: join each `alerts` row to its latest event by `(event_ts DESC, event_id DESC)`, then derive `status`, permissions, detection fields, and source score/threshold/model. Return the page in stable `(detected_at DESC, alert_id ASC)` order. Events remain immutable after insertion.

## Seed behavior

Seed the complete dataset in one transaction under a database advisory lock. On a clean database, calculate one shift `startup_utc - fixture_reference_utc`, then insert every telemetry, inference, alert, detected alert-event, and evaluation row with that shift. Preserve each original relative interval, ordering, gaps, and alert-to-inference relationship exactly. The seed includes the active demo model version. `alert_commands` is initially empty: the detected event is not command-produced, and runtime mutations create command rows. Use the known seed alert id as a sentinel: a later run that finds it verifies the seeded dataset and skips insertion, retaining the original anchor rather than shifting again. Any insertion or verification failure rolls the transaction back, so no partial seed state persists. Runtime-generated `request_id` values need only be nonempty strings.

## API contract boundary

Every success response contains only the fields accepted by its corresponding strict frontend Zod schema. All timestamps are RFC3339 with an explicit offset; serialize UTC as `Z`. All numeric fields must be finite JSON numbers; never serialize `NaN` or infinity. Register the exact `/api/model-evaluations` list route before the catch-all `/api/model-evaluations/{version:path}` detail route. Nginx forwards the raw request URI; Uvicorn decodes ASGI `scope['path']` once and Starlette passes the captured path value through. The detail handler uses `version` directly for lookup and must not call `urllib.parse.unquote` or otherwise decode it again. Encoded slashes are valid model-version content.

| Method and path | Query/body contract and resolved defaults | Response rule |
| --- | --- | --- |
| `GET /api/telemetry/latest` | optional `device_id` in `n1`…`n6` | At most six latest sensor rows with independent freshness and availability. |
| `GET /api/telemetry/history` | required `device_id`, `from`, `to`; `bucket=raw`; `limit=500` (1–5,000; bucketed max 2,000); optional cursor | Half-open telemetry points; `telemetry:<offset>` cursor. |
| `GET /api/inference-results` | required `device_id`, `from`, `to`; `bucket=raw`; `limit=500` (1–5,000; bucketed max 2,000); optional `model_version`, cursor | Seeded inference points only; top-level `model_version` is the requested value when supplied, otherwise the active seeded version; `inference:<offset>` cursor. |
| `GET /api/alert-events` | optional `alert_id`, `device_id`, `from`, `to`; `limit=200` (1–200); optional cursor | Ascending `(event_ts, event_id)` immutable events; `alert-events:<offset>` cursor. |
| `GET /api/alerts/current` | optional `device_id`, status; `page=1`, `page_size=25` (1–100) | Derived current-state page, `total`, and status-consistent action flags. |
| `POST /api/alerts/{alertId}/acknowledge` | strict JSON `{command_id, event_ts, note?}` | Durable acknowledged event and replay indicator. |
| `POST /api/alerts/{alertId}/resolve` | strict JSON `{command_id, event_ts, note?}` | Durable resolved event and replay indicator. |
| `GET /api/eda/summary` | optional `device_id`; required `from`, `to`; `bucket=raw` | On-demand scoped coverage, missingness, comparisons, and at most 500 candidates. |
| `GET /api/eda/distributions` | optional `device_id`; required `from`, `to`, field; `bins=20` (5–100) | On-demand finite summary and at most the requested bins. |
| `GET /api/eda/correlation` | optional `device_id`; required `from`, `to`; `x_field=temperature_c`, `y_field=relative_humidity_pct`; `max_points=1,000` (100–5,000); optional cursor | On-demand correlation where fields differ; `eda-correlation:<offset>` cursor. |
| `GET /api/model-evaluations` | `page=1`, `page_size=25` (1–50) | Offset page of at most 50 evaluation summaries. |
| `GET /api/model-evaluations/{version}` | catch-all path value already decoded once by Uvicorn/Starlette; use it directly as a nonempty version | One strict evaluation detail or 404; encoded slashes are valid version content. An empty captured version, including the trailing-slash detail request, is 404 Problem Details; the exact list path without a trailing slash remains the list endpoint. |
| `GET /api/system/status` | none | API/database state, telemetry observation, and an inference service row marked deferred/not ready. |
| `GET /health` | none | API-process liveness only. |
| `GET /ready` | none | API, database connectivity, and current migration revision only. |

## Query, pagination, and error rules

- Telemetry history, alert events, and EDA correlation filter point/event timestamps with `[from, to)`. Inference results use whole-window containment: `window_start_ts >= from AND window_end_ts <= to`. Required-range endpoints require both values; alert events allow either endpoint to be omitted. `from` must be earlier than `to`. M1 imposes **no maximum time-range cap**.
- Accept only buckets `raw`, `1m`, `5m`, `15m`, `1h`, and `1d`; EDA fields are `temperature_c`, `relative_humidity_pct`, and `score`.
- Cursor endpoints return `next_cursor: null` at exhaustion. Cursors are optional and opaque to callers, but M1 emits only `telemetry:<nonnegative decimal offset>`, `inference:<offset>`, `alert-events:<offset>`, and `eda-correlation:<offset>`. Treat an absent cursor as offset 0; otherwise parse its nonnegative decimal offset. When more rows remain, the next offset is `current_offset + returned_count`, rendered with the endpoint prefix; at exhaustion `next_cursor` is null. A supplied cursor that is malformed, negative, nondecimal, or has the wrong prefix returns 422.
- Offset pagination uses the per-route bounds above. `items.length <= page_size`, `total >= items.length`, and returned list counts equal `returned_count` where that field exists.
- For degenerate numeric outputs, return `correlation: null` for an empty or zero-variance sample and `coverage_pct: 0` when `expected_count` is 0. Required fields are never omitted, and no output may be non-finite.
- Invalid query or path parameters, including invalid device/status values, invalid offsets/timestamps, reversed ranges, invalid pagination, equal correlation fields, or malformed cursors return 422 `application/problem+json`. Invalid mutation JSON or mutation body schema returns 400. Every problem is the strict shape `{type,title,status,detail,instance,request_id,errors?}`.
- Missing resources return 404 Problem Details. Invalid lifecycle state, non-monotonic events, and command reuse conflicts return 409 Problem Details. Unexpected database/service failure returns 503 Problem Details. Successful responses remain strict JSON, never partial fallback objects.

## Alert transaction and idempotency algorithm

For either command route, only an omitted `note` becomes SQL `NULL`; a present string, including `""`, is retained and compared exactly without trimming. Execute one database transaction:

1. Reserve the global command identity first with `INSERT ... ON CONFLICT DO NOTHING` into `alert_commands`, storing alert id, action, event timestamp, exact nullable note, and `accepted_event_id = NULL`. A unique conflict waits for the owner transaction.
2. If the insert conflicted, read the now-canonical row. If its alert id, action, event timestamp, and exact nullable note differ, return 409. If they match, join its non-null `accepted_event_id` to `alert_events`, construct a fresh response with a fresh request id and `idempotent_replay: true`, and commit without appending an event. A reservation is never committed with a null accepted event id.
3. For a newly reserved command, `SELECT` the target `alerts` row `FOR UPDATE`; this alert-scoped lock serializes lifecycle changes. If it is absent, return 404.
4. Read its latest event by `(event_ts DESC, event_id DESC)`. Require `command.event_ts > latest.event_ts` strictly. Require `detected -> acknowledged` or `acknowledged -> resolved`; direct resolve, repeated acknowledgement, and repeated resolve return 409.
5. Insert one immutable event with a generated event id, the alert's device and detection provenance, `actor='operator'`, and the command timestamp/note. Update the reserved command's `accepted_event_id`, commit, and construct a fresh response with `idempotent_replay: false`.

No event insertion occurs on any failure. Concurrent commands for different alerts proceed independently; commands for one alert serialize through its `alerts` row lock. Event timestamp monotonicity is strict even when event ids would otherwise order ties. HTTP `request_id` is generated per response and is never stored in `alert_commands`.

## Health, readiness, and status

- `/health` returns 200 only while the FastAPI process can answer, with `status: "alive"`; it does not query the database or inference.
- `/ready` checks exactly API execution, TimescaleDB connectivity, and that the applied migration revision equals the packaged head revision. Success is HTTP 200 with the strict `ReadinessResponse` and `status: "ready"`. Failed database or migration readiness is HTTP 503 strict Problem Details, with dependency detail represented in `errors` when needed; it is not a 503 `ReadinessResponse` with `status: "not_ready"`. Rich operational observation belongs to `/api/system/status`. `/ready` does not check MQTT, a model artifact, or inference.
- `/api/system/status` is an observation snapshot, not a readiness gate. It reports API and database as observed, reports `inference-worker` with `liveness: "unknown"`, `readiness: "not_ready"`, and a detail that inference is deferred in M1, and derives telemetry age/counts from persisted rows. It may include bounded diagnostics.

## Testing and delivery gates

Implementation is acceptable only when all gates pass:

1. Migration creates exactly the six tables, two hypertables, constraints, and indexes; rerunning migrations and seed is safe.
2. Route tests exercise all 15 method/path pairs against FastAPI and parse every success/problem payload with the frontend Zod schemas.
3. Tests cover `n1`…`n6`, shifted timestamps with preserved spacing, empty results, data gaps, every default/bound, all four cursor prefixes, and malformed cursors returning 422. Boundary tests prove telemetry/events/correlation exclude a point/event at `to`, while inference includes only windows satisfying `window_start_ts >= from AND window_end_ts <= to`.
4. Transaction tests cover reservation-first identical replay without append, global `command_id` conflict after owner-transaction waiting, exact empty-string note handling, strict timestamp conflict, lifecycle conflicts, 404, and concurrent same-alert serialization through `alerts FOR UPDATE`.
5. Numeric serialization tests reject non-finite values; readiness tests require a 200 `ReadinessResponse` only for ready and a 503 Problem Details payload for database/migration failure, distinct from inference deferred system status.
6. Compose verification confirms only Nginx is host-exposed; Nginx serves the SPA and proxies the three same-origin backend prefixes; database is private; API is ready after migration and seed.
7. Nginx→Uvicorn integration tests verify model-version routing and single decoding: `release%2F2026` resolves to stored `release/2026`; `release%252F2026` resolves to the distinct stored literal `release%2F2026`; `release%20candidate` resolves to `release candidate`; `100%25stable` resolves to `100%stable`; and the exact list path selects the list handler.

## Milestone-two seam

M2 adds a private MQTT ingestion process and a private PyTorch inference process without changing public routes, response schemas, or Nginx topology. MQTT writes validated telemetry using the existing uniqueness rule. M2 may add an internal `inference_state` table for restart-safe inference without altering this M1 API contract. PyTorch then writes `inference_results`, inserts the stable `alerts` detection row, and appends its detected `alert_events` row in one transaction. Once that path is live, system status changes the inference row from deferred to its observed state; `/ready` remains limited to API, database, and migrations.

## Resolved defaults

FastAPI + TimescaleDB + Nginx; same-origin relative paths; Nginx proxy pass-through without URI replacement; `n1`…`n6`; strict Zod-compatible JSON; offset-aware RFC3339 timestamps; finite numeric output; half-open ranges; no range-duration cap; cursor and offset bounds as listed; six M1 tables with only two hypertables; immutable event-sourced alerts with stable `alerts` identity; reservation-first global command identity; alert-scoped `FOR UPDATE`; EDA computed on demand; startup-shifted sentinel-protected deterministic seed; no live MQTT/PyTorch; no retention or compression; only Nginx host-exposed.

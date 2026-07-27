# Milestone One: Backend Serving and Persistence Design

**Date:** 2026-07-21  
**Status:** revised for TALPHA; implementation intentionally deferred

## Authority and scope

This is the revised M1 backend authority. The live frontend contracts, adapters, mock handlers, and tests in `frontend/src/contracts/`, `frontend/src/api/`, `frontend/src/mocks/handlers.ts`, and their tests are the public boundary. The approved TALPHA dataset UI adaptation design and plan are the data authority. Where older backend material differs, the current frontend contracts and TALPHA authority win.

M1 is a design and implementation plan for same-origin HTTP serving with durable TimescaleDB persistence. It deliberately defers live MQTT ingestion and PyTorch inference. M1 seeds deterministic TALPHA fixture artifacts only, and `/api/system/status` reports inference as deferred, not running. This supersedes legacy six-device, Laravel, Redis, ClickHouse, MySQL, ONNX, startup-shifted, and 90-day-TTL assumptions.

### Goals

- Serve the existing frontend through Nginx and implement its 15 exact HTTP boundaries with strict Zod-compatible JSON.
- Persist TALPHA telemetry, deterministic inference fixtures, stable alert identities, immutable alert events, commands, and validation-only evaluation artifacts in TimescaleDB.
- Make alert lifecycle commands durable, serialized per alert, globally idempotent, and safe to retry.
- Keep M1 fixture-only while leaving a complete artifact-manifest seam for a later M2 runtime.

### Non-goals

- MQTT broker or client, PyTorch loading or execution, live inference, streaming, retention policies, TimescaleDB compression, caching, authentication, and frontend adaptation work.
- Extra services, public routes, tables, host-exposed ports, compatibility aliases, generic dataset adapters, runtime cross-repository reads, and fabricated metrics.
- Any test-split, model-selection, or deployment claim. The locked TALPHA `test.npz` is not an M1 seed or evaluation source.

## Canonical TALPHA data and artifact contract

Only `talpha-1` and `talpha-2` are valid public device IDs. Their public telemetry fields remain `temperature_c` and `relative_humidity_pct`.

| Device ID | Source channels after inverse min-max scaling |
| --- | --- |
| `talpha-1` | `[suhu1, rh1]`, source columns `[0, 1]` |
| `talpha-2` | `[suhu2, rh2]`, source columns `[2, 3]` |

The canonical source is the TALPHA validation corpus:

- `data/processed/talpha/metadata.json`, SHA-256 `9d015808bd032747d7b48ffdadc7f7d98aa68efb81e8e5c0d9313fbd7c77a8bc`
- `data/processed/talpha/val.npz`, SHA-256 `56c43dfd7aeb4f79e533a67e373174a07c45c2a4b1ba3df14352309e6670f2b1`
- `runs/benchmark_validation_figures/comparison/comparison_summary.json`, the validation-only comparison authority for evaluation-track metadata and thresholds

Offline validation must confirm 86,104 rows, `seg_bounds=[0,36032,65146,86104]`, three segments, and two gaps. The backend owns a checked-in seed-fixture export prepared offline from these canonical sibling sources. The runtime API, migration container, seed container, and Compose services never read the sibling repository.

The export records both source hashes, scaler minimum and maximum values, the inverse min-max formula, source channel mapping, exact source timestamp strings, and source-index provenance. It is deliberately bounded rather than a copy of all 86,104 rows:

- normal telemetry source indices `0..5`
- gap telemetry source indices `36030`, `36031`, `36032`, `36033`, `65144`, `65145`, `65146`, `65147`, with `gap_before=true` only at `36032` and `65146`
- latest telemetry source index `86103`
- inference windows `0..29`, `30..59`, `60..89`, and `90..119`

Each exported row retains the exact source timestamp interval and source index. No timestamp or chart position is reconstructed from a row index. The export must never use `test.npz`, `6device`, `PR00188-1`, legacy notebook summaries, validation-tuning outputs, or pilot artifacts as telemetry, seed, or evaluation sources.

TALPHA historical timestamps are preserved 2025 calendar values in the exact timezone-unqualified form `YYYY-MM-DDTHH:mm:ss`. TALPHA is never claimed to be UTC. The observed validation cadence is irregular: minimum 1 second, median 6 seconds, p95 8 seconds, and maximum non-gap 587 seconds. A gap exists only when adjacent timestamps differ by more than 600 seconds. M1 does not interpolate or resample source rows. Raw rows use `sample_count=1`; non-raw buckets remain SQL aggregates.

## Architecture and topology

`browser -> Nginx -> FastAPI -> TimescaleDB`

- Nginx serves the built frontend, falls back to the SPA entrypoint, and proxies `/api/`, `/health`, and `/ready` to FastAPI. Each proxy location uses `proxy_pass http://api:8000` with no URI component and no trailing slash, so Nginx forwards the unparsed request URI without replacement or normalization. Browser calls remain relative, same-origin paths.
- The backend package owns validation, response serialization, EDA queries computed on demand, migration checks, seed loading, and database transactions. The one-shot seed job invokes that code. The API runtime does not orchestrate seeding.
- TimescaleDB is the only durable store. Migration and seed jobs use the same private database network and exit after completion.
- Compose starts `db`, then one-shot `migrate`, then one-shot `seed`, then `api`, then `nginx`. API starts only after migration and seed complete successfully. Only Nginx publishes a host port. API, database, migration, and seed are private-network services.
- M1 creates no retention or compression policy.

## Persistence model

Use exactly six tables. Only `telemetry` and `inference_results` are Timescale hypertables. Historical, event, and evaluation timestamp columns use `timestamp without time zone`, never `timestamptz`. The other four tables are ordinary relational tables so `event_id` and `command_id` can be globally unique without hypertable partition-key constraints.

| Table | Identity and durable fields | Rules |
| --- | --- | --- |
| `telemetry` | `(device_id, ts)`; temperature, relative humidity, payload hash, source index | `device_id` is constrained to `talpha-1` or `talpha-2`. `ts` is `timestamp without time zone`. Matching identity and payload hash is a no-op; different content at the same identity is rejected and never overwrites history. |
| `inference_results` | `(device_id, window_end_ts, model_version)`; window start, score, threshold, anomaly flag, `score_provenance`, fixture provenance | Timestamp columns are `timestamp without time zone`. `score_provenance='deterministic_threshold_fixture'`. M1 rows are deterministic fixtures only. |
| `alerts` | stable `alert_id`; device, detected time, score, threshold, model version, `detection_basis`, source inference window provenance | `detected_at` is `timestamp without time zone`; `detection_basis='threshold_model_fixture'`. One detection row is immutable lifecycle provenance and is the row locked to serialize commands. |
| `alert_events` | globally unique immutable `event_id`; alert id, event timestamp/type, actor, nullable note, inference-window provenance, `detection_basis` | `event_ts` is `timestamp without time zone`. Append-only ledger. Lifecycle state is derived from these rows. All events carry the alert fixture detection basis required by the strict frontend schema. |
| `alert_commands` | global `command_id`; canonical alert id, action, event timestamp, exact nullable note, nullable accepted event id | `event_ts` is `timestamp without time zone`. One row reserves every accepted command identity and makes replay durable. It stores no HTTP response or request ID. |
| `model_evaluations` | `version`; validation-track fields, hashes, metric declarations and values, nullable notes | Stores the current `ValidationTrackFieldsSchema` fields: `model`, `track`, `label`, `score_key`, `score_semantics`, `evaluation_period`, `validation_only`, `test_evaluated`, `n_val_windows`, `threshold`, `threshold_policy`, `has_labeled_ground_truth`, `available_metrics`, and `summary`. No fabricated `created_at`, performance curves, matrix, or ranking fields are stored. |

`threshold_policy`, `available_metrics`, and `metrics` are JSONB. The current seed has `validation_only=true`, `test_evaluated=false`, and `has_labeled_ground_truth=false` for every evaluation row. It exposes only the contract-accepted calibration metrics `threshold`, `strict_exceedance_count`, and `strict_exceedance_fraction`; labeled structures and undeclared metrics are absent.

`/api/alerts/current` joins each `alerts` row to its latest event by `(event_ts DESC, event_id DESC)`, derives status and permissions, and returns stable `(detected_at DESC, alert_id ASC)` order. Events remain immutable after insertion.

## Seed behavior

The checked-in backend fixture export is prepared offline once from the canonical TALPHA sources and then loaded locally by the seed job. It includes source hashes and provenance, but it does not include a cross-repository path that the runtime can read. Seed all rows in one transaction under a database advisory lock. Do not shift any timestamp at startup. Preserve source calendar values, exact source intervals, ordering, source indices, segment boundaries, gaps, and alert-to-inference relationship exactly.

Seed telemetry from the bounded normal, gap, and latest selections described above for both TALPHA devices. Seed four 30-reading windows per device, stride 1, without crossing `seg_bounds`; each event time is the window-end timestamp. A window is a 30-reading sequence, not a five-minute duration.

Real Arm B score arrays are unavailable. Per-node inference is a deterministic threshold fixture, not runtime inference, recovered model output, or ground truth:

| Device | Model version | Threshold | Seeded fixture scores |
| --- | --- | ---: | --- |
| `talpha-1` | `conv1d-arm-b-talpha-1-validation-fixture` | `0.02707822278141974` | `[0.013, 0.019, threshold, 0.028]` |
| `talpha-2` | `conv1d-arm-b-talpha-2-validation-fixture` | `0.031537856459617604` | `[0.014, 0.022, threshold, 0.025]` |

`is_anomaly` is always the strict comparison `score > threshold`. The one approved active alert is seeded from the TALPHA-1 final anomalous seeded inference window with score `0.028`, identity `alert_talpha_1_active`, detected event `event_talpha_1_detected`, actor `threshold-model-fixture`, and `detection_basis='threshold_model_fixture'`. This is fixture-only detection provenance, never a runtime-inference or incident claim. `alert_commands` starts empty because the detected event is not command-produced.

The seed includes exactly these seven validation-only tracks, with strict validation p99.5 `>` thresholds:

| Version | Model and track | Label | Score key | Threshold |
| --- | --- | --- | --- | ---: |
| `ewma-canonical-4ch` | `ewma`, `canonical_4ch` | EWMA | `global_mae` | `0.047478773146867714` |
| `pca-canonical-4ch` | `pca`, `canonical_4ch` | PCA | `global_mae` | `0.057222952693700785` |
| `conv1d-arm-a` | `conv1d_autoencoder`, `arm_a` | Conv1D Arm A | `global_mae` | `0.025718613043427447` |
| `conv1d-arm-b-talpha1` | `conv1d_autoencoder`, `arm_b_talpha1` | Conv1D Arm B TALPHA-1 | `global_mae` | `0.02707822278141974` |
| `conv1d-arm-b-talpha2` | `conv1d_autoencoder`, `arm_b_talpha2` | Conv1D Arm B TALPHA-2 | `global_mae` | `0.031537856459617604` |
| `tranad-canonical-4ch` | `tranad`, `canonical_4ch` | TranAD | `averaged_global_mse` | `0.007528403326869005` |
| `usad-canonical-4ch` | `usad`, `canonical_4ch` | USAD | `averaged_global_mse` | `0.008044914752244947` |

EWMA, PCA, and Conv1D use global mean absolute reconstruction error. TranAD and USAD use the average of two global mean squared reconstruction errors. Every track has `n_val_windows=86017`, `validation_only=true`, `test_evaluated=false`, `has_labeled_ground_truth=false`, `threshold_policy={source_split:'val', percentile:99.5, comparison:'>'}`, `strict_exceedance_count=431`, and `strict_exceedance_fraction=0.005010637432135508`. No evaluation seed supplies or implies a confusion matrix, ROC, precision-recall curve, F1, accuracy, ranking, test result, selected model, or deployment claim.

Use the known seed alert ID as a sentinel. A later run verifies the same static fixture hashes, counts, identities, and provenance, then skips insertion. Any insertion or verification failure rolls back the whole transaction, so no partial seed state persists. Runtime-generated timestamps, including request and health timestamps, must be emitted in the current strict no-offset `YYYY-MM-DDTHH:mm:ss` contract. That formatting does not assert a TALPHA timezone.

## API contract boundary

Every success response contains only fields accepted by its corresponding strict frontend Zod schema. Historical, event, and runtime-generated API timestamps use exact no-offset `YYYY-MM-DDTHH:mm:ss` values. Do not append `Z`, an offset, or a TALPHA timezone assertion. All numeric fields are finite JSON numbers, never `NaN` or infinity. Register `/api/model-evaluations` before `/api/model-evaluations/{version:path}`. Nginx forwards the raw request URI, Uvicorn decodes ASGI `scope['path']` once, and Starlette passes the captured version through. The detail handler uses `version` directly and never decodes it again. Encoded slashes remain valid model-version content.

| Method and path | Query/body contract and defaults | Response rule |
| --- | --- | --- |
| `GET /api/telemetry/latest` | optional `device_id` in the two TALPHA IDs | At most two latest sensor rows with independent freshness and availability. |
| `GET /api/telemetry/history` | required TALPHA `device_id`, `from`, `to`; `bucket=raw`; `limit=500` (1 to 5,000, bucketed max 2,000); optional cursor | Half-open telemetry points; `telemetry:<offset>` cursor. |
| `GET /api/inference-results` | required TALPHA `device_id`, `from`, `to`; `bucket=raw`; `limit=500` (1 to 5,000, bucketed max 2,000); optional `model_version`, cursor | Deterministic fixture points only; `inference:<offset>` cursor. |
| `GET /api/alert-events` | optional `alert_id`, TALPHA `device_id`, `from`, `to`; `limit=200` (1 to 200); optional cursor | Ascending immutable events; `alert-events:<offset>` cursor. |
| `GET /api/alerts/current` | optional TALPHA `device_id`, status; `page=1`, `page_size=25` (1 to 100) | Derived current-state page, total, and status-consistent action flags. |
| `POST /api/alerts/{alertId}/acknowledge` | strict JSON `{command_id, event_ts, note?}` | Durable acknowledged event and replay indicator. |
| `POST /api/alerts/{alertId}/resolve` | strict JSON `{command_id, event_ts, note?}` | Durable resolved event and replay indicator. |
| `GET /api/eda/summary` | optional TALPHA `device_id`; required `from`, `to`; `bucket=raw` | On-demand scoped coverage, missingness, comparisons, and at most 500 candidates. |
| `GET /api/eda/distributions` | optional TALPHA `device_id`; required `from`, `to`, field; `bins=20` (5 to 100) | On-demand finite summary and requested bins. |
| `GET /api/eda/correlation` | optional TALPHA `device_id`; required `from`, `to`; `x_field=temperature_c`, `y_field=relative_humidity_pct`; `max_points=1,000` (100 to 5,000); optional cursor | On-demand correlation where fields differ; `eda-correlation:<offset>` cursor. |
| `GET /api/model-evaluations` | `page=1`, `page_size=25` (1 to 50) | Offset page of at most 50 validation-track summaries. |
| `GET /api/model-evaluations/{version}` | already single-decoded nonempty version | One strict validation-track detail or 404. An empty trailing detail path is 404 Problem Details. |
| `GET /api/system/status` | none | API/database observation, TALPHA fixture telemetry observation, and deferred inference row. |
| `GET /health` | none | API-process liveness only. |
| `GET /ready` | none | API, database connectivity, and current migration revision only. |

## Query, pagination, and error rules

- Telemetry history, alert events, and EDA correlation filter timestamps with `[from, to)`. Inference results require whole-window containment: `window_start_ts >= from AND window_end_ts <= to`. Required-range endpoints require both values; alert events allow either endpoint to be omitted. `from` must be earlier than `to`. M1 has no maximum range-duration cap.
- Accepted buckets are `raw`, `1m`, `5m`, `15m`, `1h`, and `1d`; EDA fields are `temperature_c`, `relative_humidity_pct`, and `score`. Bucketing is SQL aggregation only, not interpolation or a source-cadence claim.
- Cursor endpoints return `next_cursor: null` at exhaustion. M1 emits only `telemetry:<nonnegative decimal offset>`, `inference:<offset>`, `alert-events:<offset>`, and `eda-correlation:<offset>`. Malformed, negative, nondecimal, or wrong-prefix cursors return 422.
- `raw` telemetry returns `sample_count=1`; non-raw output has `sample_count=count(rows)`, aggregate temperature/RH values, and bucket-start timestamps. No synthetic empty bucket is returned. Raw `gap_before` derives only from an adjacent delta greater than 600 seconds. Bucket gaps are based on absent aggregate rows, not an assumed source interval.
- For degenerate numeric outputs, return `correlation: null` for an empty or zero-variance sample and `coverage_pct: 0` when `expected_count` is 0. Required fields are never omitted, and no output may be non-finite.
- Invalid query or path parameters, including a non-TALPHA ID, malformed no-offset timestamp, reversed range, invalid pagination, equal correlation fields, or malformed cursor return 422 `application/problem+json`. Invalid mutation JSON or body schema returns 400. Every problem is `{type,title,status,detail,instance,request_id,errors?}`.
- Missing resources return 404 Problem Details. Invalid lifecycle state, non-monotonic events, and command-reuse conflicts return 409. Unexpected database or service failures return 503. Success responses remain strict JSON, never partial fallback objects.

## Alert transaction and idempotency algorithm

For either command route, only an omitted `note` becomes SQL `NULL`; a present string, including `""`, is retained and compared exactly without trimming. Execute one database transaction:

1. Reserve the global command identity first with `INSERT ... ON CONFLICT DO NOTHING` into `alert_commands`, storing alert ID, action, event timestamp, exact nullable note, and `accepted_event_id = NULL`. A unique conflict waits for the owner transaction.
2. If the insert conflicted, read the canonical row. If its alert ID, action, event timestamp, or exact nullable note differs, return 409. If they match, join its non-null `accepted_event_id` to `alert_events`, construct a response with a fresh request ID and `idempotent_replay: true`, then commit without appending an event. A reservation never commits with a null accepted event ID.
3. For a newly reserved command, `SELECT` the target `alerts` row `FOR UPDATE`; this alert-scoped lock serializes lifecycle changes. If it is absent, return 404.
4. Read its latest event by `(event_ts DESC, event_id DESC)`. Require `command.event_ts > latest.event_ts` strictly. Require `detected -> acknowledged` or `acknowledged -> resolved`; direct resolution, repeated acknowledgement, and repeated resolution return 409.
5. Insert one immutable event with a generated event ID, the alert's TALPHA detection provenance, `detection_basis='threshold_model_fixture'`, command timestamp, and note. Update the reserved command's `accepted_event_id`, commit, and construct a response with `idempotent_replay: false`.

No event insertion occurs on failure. Commands for different alerts proceed independently; commands for one alert serialize through its `alerts` row lock. Event timestamp monotonicity is strict even when event IDs would otherwise order ties. HTTP `request_id` is generated per response and is never stored in `alert_commands`.

## Health, readiness, and status

- `/health` returns 200 only while FastAPI can answer, with `status: "alive"`. It does not query the database or inference.
- `/ready` checks exactly API execution, TimescaleDB connectivity, and that the applied migration revision equals packaged head. Success is HTTP 200 with the strict `ReadinessResponse` and `status: "ready"`. Database or migration failure is HTTP 503 strict Problem Details, not a success-shaped not-ready body. `/ready` does not check MQTT, model artifacts, or inference.
- `/api/system/status` is an observation snapshot, not a readiness gate. It reports API and database as observed, reports `inference-worker` with `liveness: "unknown"`, `readiness: "not_ready"`, and a detail that inference is deferred in M1, and derives telemetry age and counts from persisted TALPHA fixture rows. It may include bounded diagnostics.

## Testing and delivery gates

After separate implementation authorization, two lanes may start together against the approved, frozen TALPHA contract:

- **Frontend Lane** owns frontend fixture, handler, UI, and test reconciliation under the existing approved TALPHA adaptation plan.
- **Backend Lane** owns backend Tasks 1 through 12 and the backend/root-only portions of Task 13.

If either lane proposes a public contract change, pause both affected contract-facing tasks and reconcile the contract before either resumes. Task 13 frontend/Nginx finalization and Tasks 14 through 16 are join gates that require both lanes to complete. The acceptance gates are:

1. Migration creates exactly six tables, two hypertables, TALPHA constraints, `timestamp without time zone` timestamp columns, `score_provenance`, `detection_basis`, and model-evaluation validation-track fields. Rerunning migrations and seed is safe.
2. Route tests exercise all 15 method/path pairs against FastAPI and parse every success/problem payload with current frontend Zod schemas.
3. Tests cover only `talpha-1` and `talpha-2`, rejection of `n1` through `n6`, strict no-offset historical and runtime timestamp formatting, no startup shifting, bounded source-index selections, the two >600-second gaps, irregular cadence facts, raw `sample_count=1`, bucket aggregation, and all defaults, bounds, cursor prefixes, and half-open or whole-window boundaries.
4. Inference tests prove 30 readings, stride 1, no segment crossing, event time at window end, exact node thresholds, strict equality not being anomalous, deterministic score provenance, and the one TALPHA-1 fixture alert. They must not treat fixture scores as runtime outputs or ground truth.
5. Evaluation tests expose exactly the seven named validation-only tracks, `n_val_windows=86017`, threshold-policy `val` p99.5 strict `>`, accepted calibration metrics only, null hashes where the current contracts permit them, and no labeled structures, test evidence, ranking, or performance claims.
6. Transaction tests cover reservation-first identical replay without append, global `command_id` conflict after owner-transaction waiting, exact empty-string note handling, strict timestamp conflict, lifecycle conflicts, 404, and concurrent same-alert serialization through `alerts FOR UPDATE`.
7. Numeric serialization tests reject non-finite values. Readiness tests require a 200 `ReadinessResponse` only when ready and a 503 Problem Details payload for database or migration failure, distinct from deferred inference system status.
8. Compose verification confirms only Nginx is host-exposed; Nginx serves the SPA and proxies the three same-origin backend prefixes; database is private; API starts after migration and seed; no retention or compression exists.
9. Nginx to Uvicorn integration verifies single decoding: `release%2F2026` resolves to `release/2026`; `release%252F2026` resolves to literal `release%2F2026`; `release%20candidate` resolves to `release candidate`; `100%25stable` resolves to `100%stable`; and the exact list path selects the list handler.

## Milestone-two seam

M2 may add a private MQTT ingestion process and a private PyTorch inference process without changing public routes, response schemas, alert transaction semantics, or Nginx topology. Before any runtime model work, it must consume a portable manifest that bundles:

- schema and feature order or mapping
- scaler values and inverse-scaling formula
- `(0,200)` filter
- timestamp and timezone policy without claiming a TALPHA timezone
- the `>600s` gap rule
- 30-reading, stride-1 windowing and window-end event time
- model architecture configuration and checkpoint
- selected epoch, arm, and channel indices
- score formula and score key
- threshold source, value, and strict comparison
- runtime compatibility requirements
- a SHA-256 for every bundled artifact

The active-model pointer remains unset until final locked-test evaluation and model selection exist. M2 must not backfill a selection from the M1 validation fixtures. When live ingestion is introduced, it writes validated telemetry using the existing uniqueness rule. When live inference is introduced, it writes `inference_results`, the stable `alerts` detection row, and its detected `alert_events` row in one transaction. Only then may system status replace the M1 deferred inference observation.

## Resolved defaults

FastAPI + TimescaleDB + Nginx; same-origin relative paths; Nginx proxy pass-through without URI replacement; `talpha-1` and `talpha-2`; public `temperature_c` and `relative_humidity_pct`; strict no-offset historical timestamps; finite numeric output; half-open ranges; no range-duration cap; SQL aggregation buckets; six M1 tables with only two hypertables; `timestamp without time zone`; immutable event-sourced alerts; reservation-first global command identity; alert-scoped `FOR UPDATE`; EDA computed on demand; checked-in bounded TALPHA fixture export with no startup shift or runtime sibling read; deterministic threshold fixtures only; no live MQTT or PyTorch; no retention or compression.

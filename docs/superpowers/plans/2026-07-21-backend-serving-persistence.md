# Backend Serving and Persistence Implementation Plan

**Status:** revised for TALPHA; plan only, implementation intentionally deferred

**Goal:** Define the M1 same-origin FastAPI and TimescaleDB backend that can later serve the reconciled TALPHA frontend with durable, bounded, deterministic fixture data. This document does not authorize implementation now.

**Architecture:** `browser -> nginx -> FastAPI -> TimescaleDB`. Compose retains private `db`, one-shot `migrate`, one-shot `seed`, private `api`, and public `nginx`. The seed is checked-in, deterministic, advisory-lock protected, and idempotent. It never shifts timestamps and never reads a sibling repository at runtime.

**Technology:** Python 3.13, FastAPI 0.139.2, Pydantic 2.13.4, Uvicorn 0.51.0, SQLAlchemy asyncio 2.0.51, psycopg 3.3.2, Alembic 1.18.5, PostgreSQL 17 with TimescaleDB 2.28.3, Nginx, and the existing React/Vite, Vitest, and Playwright tooling.

## Global constraints

- **PLAN ONLY.** Do not implement, install, build, test, run Docker, generate data, or run Git while this plan remains deferred.
- Keep direct dependency pins: `fastapi==0.139.2`, `pydantic==2.13.4`, `uvicorn==0.51.0`, `sqlalchemy[asyncio]==2.0.51`, `psycopg[binary]==3.3.2`, and `alembic==1.18.5`; test pins are `pytest==9.1.0`, `httpx==0.28.1`, and `anyio==4.14.2`. Use `timescale/timescaledb:2.28.3-pg17`; add no package manager or lock tool.
- The current frontend contracts, adapters, mock handlers, and tests are the public boundary. They accept only `talpha-1` and `talpha-2`; no `n1` through `n6` alias is allowed.
- Public telemetry stays `temperature_c` and `relative_humidity_pct`. Offline source mapping after inverse min-max scaling is TALPHA-1 `[suhu1,rh1]` or columns `[0,1]`, and TALPHA-2 `[suhu2,rh2]` or columns `[2,3]`.
- Historical, event, and evaluation timestamps use the strict no-offset form `YYYY-MM-DDTHH:mm:ss` and PostgreSQL `timestamp without time zone`. Preserve source 2025 calendar values. Do not append `Z`, assert TALPHA UTC, or shift fixture timestamps on startup. Runtime-generated timestamps must use the same strict format without making a TALPHA timezone claim.
- M1 has no MQTT, PyTorch runtime, Redis, Celery, authentication, retention, compression, repository layer, cache, extra service, route, table, port, compatibility map, or generic dataset adapter. `/api/system/status` reports inference as deferred.
- Seed data is a backend-owned checked-in fixture export prepared offline from the canonical sibling corpus. Runtime API, migrations, seed containers, and Compose services never read the sibling repository.
- Do not use the locked `test.npz`, `6device`, `PR00188-1`, legacy notebook summaries, validation-tuning outputs, or stale pilot artifacts as a seed or evaluation source.
- Successful JSON contains only strict frontend-schema fields. Values are finite. Problems are strict `application/problem+json` objects: `{type,title,status,detail,instance,request_id,errors?}`.
- Invalid query, path, cursor, range, or pagination values return 422. Malformed mutation JSON or body returns 400. Missing resource is 404. Lifecycle, timestamp, and command conflicts are 409. Unexpected database or service failure is 503.

## TALPHA fixture authority

The offline export is derived only from:

| Canonical source | SHA-256 |
| --- | --- |
| `data/processed/talpha/metadata.json` | `9d015808bd032747d7b48ffdadc7f7d98aa68efb81e8e5c0d9313fbd7c77a8bc` |
| `data/processed/talpha/val.npz` | `56c43dfd7aeb4f79e533a67e373174a07c45c2a4b1ba3df14352309e6670f2b1` |

`runs/benchmark_validation_figures/comparison/comparison_summary.json` is the validation-only authority for the seven evaluation tracks and their thresholds. Offline preparation validates 86,104 validation rows, `seg_bounds=[0,36032,65146,86104]`, three segments, and two gaps. It records source hashes, scaler values, inverse min-max formula, channel mapping, exact no-offset source timestamp strings, and source index provenance. The checked-in export contains only:

- normal telemetry indices `0..5`
- gap telemetry indices `36030`, `36031`, `36032`, `36033`, `65144`, `65145`, `65146`, `65147`, with `gap_before=true` only at `36032` and `65146`
- latest telemetry index `86103`
- inference source-index windows `0..29`, `30..59`, `60..89`, `90..119`

Preserve exact source timestamp intervals and source index provenance. Observed validation cadence is irregular: minimum 1 second, median 6 seconds, p95 8 seconds, maximum non-gap 587 seconds. A gap is only an adjacent delta greater than 600 seconds. No interpolation or resampling is permitted. Raw rows have `sample_count=1`; non-raw requests remain SQL aggregation.

## Target file tree

```text
compose.yaml
.env.example
.gitignore
backend/
  alembic.ini
  pyproject.toml
  Dockerfile
  migrations/
    env.py
    script.py.mako
    versions/20260721_0001_m1_schema.py
  anomaly_backend/
    __init__.py
    config.py
    db.py
    tables.py
    contracts.py
    problems.py
    seed.py
    fixtures/talpha_seed.json
    main.py
    routes/__init__.py
    routes/{telemetry,inference,alerts,eda,evaluations,system}.py
    sql/__init__.py
    sql/{telemetry,inference,alerts,eda,evaluations,system}.py
  tests/
    conftest.py
    test_contracts.py
    test_db.py
    test_migration.py
    test_seed.py
    test_problems.py
    test_telemetry_inference.py
    test_alert_reads.py
    test_alert_commands.py
    test_eda.py
    test_evaluations.py
    test_system.py
    test_app.py
frontend/
  vitest.contract.config.ts
  playwright.real.config.ts
  tests/contract/m1-real-backend.contract.ts
  tests/e2e-real/{helpers,m1.spec}.ts
```

The backend fixture export is the only new fixture surface. Frontend code and fixtures are outside this backend plan.

## Parallel lanes and join gates

After separate implementation authorization, execution uses two lanes against the approved, frozen TALPHA public contract. This document remains plan-only and does not grant that authorization.

| Lane or join gate | Ownership and dependency graph | File-content boundary |
| --- | --- | --- |
| Frontend Lane | External lane: execute the existing approved `2026-07-21-talpha-dataset-ui-adaptation.md` plan for frontend fixture, handler, UI, and test reconciliation. Its implementation tasks are not duplicated here. | Owns all frontend reconciliation files and hands off the reconciled frontend contract and file ownership. |
| Backend Lane | Runs concurrently with the Frontend Lane: Tasks `1 -> 2 -> 3 -> 4`, then Tasks 5 through 11 in their documented backend dependency order, then Task 12. Backend/root-only Compose preparation from Task 13 may proceed when its backend prerequisites are ready. | Owns backend files and root/backend Compose files. It makes no edit under `frontend/`. |
| Contract-change pause | If either lane proposes a public-contract change, pause both affected contract-facing tasks, reconcile against the approved TALPHA authority and current Zod schemas, then resume only with the shared contract frozen again. | No unilateral public-contract edit. |
| Integration join | Task 13 frontend/Nginx finalization begins only after both lanes complete and the Frontend Lane hands off. | Any `frontend/` edit, including `frontend/nginx.conf` and package scripts, waits for the handoff to prevent file contention. |
| Verification join | Tasks 14, 15, and 16 require both lanes and Task 13 final integration. | Isolated frontend real-backend lanes remain join-gate work, not a prerequisite for Backend Tasks 1 through 12. |

---

### Task 1: Contract helpers and package foundation

**Files:** Create the package, Docker, settings, contracts, route and SQL package markers, and `backend/tests/test_contracts.py` listed in the target tree.

**Interfaces:** Mirror the live Zod schemas in `frontend/src/contracts/{common,telemetry,inference,alerts,eda,modelEvaluation,systemHealth}.ts`. Define only `talpha-1` and `talpha-2` device literals; bucket and EDA-field literals remain unchanged. Implement strict no-offset timestamp parsing and lexical historical-time comparisons, `parse_cursor`, `make_cursor`, finite-number checks, and strict Pydantic request and response models.

- [ ] **Step 1:** Add failing contract tests for the two IDs, rejection of all six legacy IDs, strict no-offset timestamps, cursor arithmetic, finite values, and strict response shapes.
- [ ] **Step 2:** Define a `HistoricalDateTime` validator matching `YYYY-MM-DDTHH:mm:ss` exactly. It must accept no `Z` or offset and use lexical ordering for range comparisons.
- [ ] **Step 3:** Define `ScoreProvenance` as only `deterministic_threshold_fixture` and `DetectionBasis` as only `threshold_model_fixture`.
- [ ] **Step 4:** Define `ValidationTrackFields` matching the frontend fields exactly: version, model, track, label, score key and semantics, evaluation period, validation-only and test flags, validation-window count, threshold, threshold policy, labeled-ground-truth flag, declared metrics, and summary.
- [ ] **Step 5:** Specify M1 freshness from persisted observation without any five-minute source-cadence assumption. Do not infer gaps or coverage from equal spacing. Raw rows have `sample_count=1`; SQL aggregation governs bucketed rows.
- [ ] **Step 6:** The eventual focused test proves strict schemas accept only the two TALPHA IDs, no-offset timestamps, finite values, and scoped cursors.

---

### Task 2: Database and Compose foundation

**Files:** Create `compose.yaml`, `.env.example`, backend DB/table modules, and database test scaffolding. Modify `.gitignore` only for local environment values.

**Interfaces:** Use Core `Table` objects and one `AsyncEngine`; no ORM mappings, sessions, sessionmaker, or repository layer. Compose contains private `db`, and later Tasks 3 and 13 add the approved migration, seed, API, and Nginx chain.

- [ ] **Step 1:** Define settings from only `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD`.
- [ ] **Step 2:** Define a private internal Compose network and no database host port.
- [ ] **Step 3:** Add database health and migration-revision helpers using the injected Core connection.
- [ ] **Step 4:** Add tests that establish Core-engine ownership and assert the private database topology without introducing a sixth service.

---

### Task 3: Alembic migration for six tables and two hypertables

**Files:** Create Alembic configuration and revision `20260721_0001_m1_schema.py`; modify table metadata and migration tests.

**Interfaces:** Create exactly `telemetry`, `inference_results`, `alerts`, `alert_events`, `alert_commands`, and `model_evaluations`. Only `telemetry` and `inference_results` become hypertables. No foreign key may target a hypertable.

- [ ] **Step 1:** Add migration assertions for exactly six tables, exactly two hypertables, no retention/compression policy, TALPHA device checks, and no foreign key to a hypertable.
- [ ] **Step 2:** Define `telemetry.device_id` and `inference_results.device_id` checks for only `talpha-1` and `talpha-2`; all `ts`, `window_start_ts`, and `window_end_ts` columns are `timestamp without time zone`.
- [ ] **Step 3:** Define `inference_results` with finite score and threshold checks, `window_start_ts < window_end_ts`, `score_provenance text NOT NULL CHECK (score_provenance = 'deterministic_threshold_fixture')`, source-index window provenance, and a primary key of `(device_id, window_end_ts, model_version)`.
- [ ] **Step 4:** Define `alerts` with no-offset `detected_at`, score, threshold, model version, source window provenance, and `detection_basis text NOT NULL CHECK (detection_basis = 'threshold_model_fixture')`. Validate source inference provenance in application code, not with an invalid hypertable foreign key.
- [ ] **Step 5:** Define append-only `alert_events` with no-offset `event_ts`, lifecycle check, nullable note, optional inference window/model fields, and non-null `detection_basis`. Add the stable alert and event ordering indexes.
- [ ] **Step 6:** Define `alert_commands` with global `command_id`, no-offset event timestamp, exact nullable note, nullable accepted event ID, and its alert index.
- [ ] **Step 7:** Define `model_evaluations` without fabricated creation time. Persist validation-track scalar columns plus JSONB `threshold_policy`, `available_metrics`, and `metrics`, nullable hashes and notes, and no columns for confusion matrices, ROC, precision-recall, F1, accuracy, or rankings.
- [ ] **Step 8:** The eventual migration test reruns upgrade safely and confirms all historical, event, and evaluation timestamp fields use `timestamp without time zone`.

---

### Task 4: Deterministic TALPHA seed job

**Files:** Create `backend/anomaly_backend/fixtures/talpha_seed.json`, `seed.py`, and seed tests; modify tables and Compose only to package and execute this local fixture.

**Interfaces:** `talpha_seed.json` is a checked-in backend export prepared offline. It contains canonical source hashes, metadata facts, scaler values and formula, channel mapping, exact source timestamp strings, source indexes, bounded telemetry records, four per-node inference windows, one detected alert, and seven evaluation records. `seed_database(conn)` reads only this file from the backend image.

- [ ] **Step 1:** Write seed tests for advisory locking, one transaction, source-hash verification, no startup shift, sentinel replay, and rollback after injected failure.
- [ ] **Step 2:** Define offline export validation for metadata hash `9d015808bd032747d7b48ffdadc7f7d98aa68efb81e8e5c0d9313fbd7c77a8bc`, NPZ hash `56c43dfd7aeb4f79e533a67e373174a07c45c2a4b1ba3df14352309e6670f2b1`, 86,104 rows, `seg_bounds=[0,36032,65146,86104]`, three segments, two gaps, and only the authorized bounded index selections.
- [ ] **Step 3:** Insert exact no-offset source calendar timestamps for telemetry indices `0..5`, the eight gap indices, and index `86103`, with source index provenance. Set `gap_before=true` only on `36032` and `65146`.
- [ ] **Step 4:** Insert four per-node inference windows `0..29`, `30..59`, `60..89`, and `90..119`. Each holds 30 readings, stride 1, stays inside one segment, and uses its final reading timestamp as `window_end_ts` and alert event time.
- [ ] **Step 5:** Insert deterministic fixture scores and strict anomaly flags. TALPHA-1 uses threshold `0.02707822278141974` with `[0.013,0.019,threshold,0.028]`; TALPHA-2 uses `0.031537856459617604` with `[0.014,0.022,threshold,0.025]`. Persist `score_provenance='deterministic_threshold_fixture'`.
- [ ] **Step 6:** Seed only `alert_talpha_1_active` from the TALPHA-1 final anomalous seeded inference window with score `0.028`, event `event_talpha_1_detected`, actor `threshold-model-fixture`, and `detection_basis='threshold_model_fixture'`. Leave `alert_commands` empty. State in fixture notes that this is not runtime inference or ground truth.
- [ ] **Step 7:** Seed exactly seven validation-only tracks: EWMA (`ewma`, `canonical_4ch`, `global_mae`), PCA (`pca`, `canonical_4ch`, `global_mae`), Conv1D Arm A (`conv1d_autoencoder`, `arm_a`, `global_mae`), Conv1D Arm B TALPHA-1 (`conv1d_autoencoder`, `arm_b_talpha1`, `global_mae`), Conv1D Arm B TALPHA-2 (`conv1d_autoencoder`, `arm_b_talpha2`, `global_mae`), TranAD (`tranad`, `canonical_4ch`, `averaged_global_mse`), and USAD (`usad`, `canonical_4ch`, `averaged_global_mse`). Use these thresholds in that order: `0.047478773146867714`, `0.057222952693700785`, `0.025718613043427447`, `0.02707822278141974`, `0.031537856459617604`, `0.007528403326869005`, and `0.008044914752244947`.
- [ ] **Step 8:** Set every evaluation to `n_val_windows=86017`, `validation_only=true`, `test_evaluated=false`, `has_labeled_ground_truth=false`, and `threshold_policy={source_split:'val', percentile:99.5, comparison:'>'}`. Expose only accepted calibration metrics: `threshold`, `strict_exceedance_count=431`, and `strict_exceedance_fraction=0.005010637432135508`.
- [ ] **Step 9:** Use `alert_talpha_1_active` as the sentinel. A repeat seed verifies static identities, fixture metadata, source hashes, counts, and provenance, then makes no changes.

---

### Task 5: Problem Details and request validation boundary

**Files:** Create problems and app-factory modules and tests; modify contracts and test scaffolding.

**Interfaces:** Produce strict Problem Details, `create_app`, and connection dependency. Preserve `redirect_slashes=False`.

- [ ] **Step 1:** Add failing tests for 400 body validation, 422 query/path validation, 404, 409, 503, strict keys, and fresh response request IDs.
- [ ] **Step 2:** Map malformed no-offset timestamps, legacy IDs, reversed lexical timestamp ranges, invalid cursors, invalid bounds, and equal correlation fields to 422.
- [ ] **Step 3:** Map malformed mutation bodies to 400, missing alert or evaluation to 404, lifecycle or command conflicts to 409, and SQL/dependency failure to 503.
- [ ] **Step 4:** Ensure runtime-generated `checked_at` and equivalent fields serialize as strict no-offset timestamps without asserting a TALPHA timezone.

---

### Task 6: Telemetry and seeded-inference reads

**Files:** Create telemetry and inference SQL/routes and `test_telemetry_inference.py`.

**Interfaces:** Produce only `GET /api/telemetry/latest`, `GET /api/telemetry/history`, and `GET /api/inference-results`.

- [ ] **Step 1:** Write failing route tests for exactly two latest rows, all six legacy IDs rejected, no-offset timestamps, raw and bucketed histories, cursor arithmetic, two >600-second gaps, inference model filtering, and whole-window selection.
- [ ] **Step 2:** Use telemetry predicate `ts >= :from_ts AND ts < :to_ts`. Use inference predicate `window_start_ts >= :from_ts AND window_end_ts <= :to_ts` and order inference by `window_end_ts ASC, model_version ASC`.
- [ ] **Step 3:** Return raw source rows with `sample_count=1` and true source gaps. For non-raw buckets, use SQL aggregate rows with no synthetic empty intervals, no interpolation, and no assertion of source cadence.
- [ ] **Step 4:** Return fixture `is_anomaly` exactly as stored from strict `score > threshold`, never recomputed from a query or claimed as live inference. Include current-contract `score_provenance` and fixture model versions.
- [ ] **Step 5:** Calculate freshness from persisted observation policy without calling the irregular TALPHA source a fixed cadence.

---

### Task 7: Alert projection and immutable event reads

**Files:** Create alert SQL/read routes and `test_alert_reads.py`.

**Interfaces:** Produce only `GET /api/alert-events` and `GET /api/alerts/current` using the existing event projection.

- [ ] **Step 1:** Add failing tests for immutable ascending events, `[from,to)`, event cursor arithmetic, TALPHA ID filtering, no-offset timestamps, detection basis, and current-page order `(detected_at DESC, alert_id ASC)`.
- [ ] **Step 2:** Derive lifecycle state from the latest event ordered by `(event_ts DESC,event_id DESC)` and preserve detected, acknowledged, and resolved permission flags.
- [ ] **Step 3:** Serialize `detection_basis='threshold_model_fixture'` on current alerts and every alert event, with nullable inference fields only as current strict contracts allow.
- [ ] **Step 4:** Assert the approved seeded alert remains explicitly fixture-only and carries the TALPHA-1 source window, score, threshold, model version, and actor provenance.

---

### Task 8: Durable reservation-first alert commands

**Files:** Extend alert SQL/routes and create `test_alert_commands.py`.

**Interfaces:** Add only acknowledge and resolve command behavior to the existing alert router. Each request gets its own Core connection; concurrency tests use separate connections.

- [ ] **Step 1:** Add failing tests for identical replay without a new event, global command reuse conflict, empty-string notes, missing alert, direct resolve, repeated action, non-monotonic no-offset timestamp, and concurrent same-alert commands.
- [ ] **Step 2:** Reserve `command_id` before locking the alert with `INSERT ... ON CONFLICT DO NOTHING`. On conflict, wait for and read the canonical command row before deciding replay or 409.
- [ ] **Step 3:** Lock the target alert with `SELECT ... FOR UPDATE`, require strict `event_ts > latest.event_ts`, accept only `detected -> acknowledged` or `acknowledged -> resolved`, append one event, then set `accepted_event_id` before commit.
- [ ] **Step 4:** Preserve exact note semantics. Only omission becomes SQL `NULL`; `""` stays `""`; no trimming occurs. No failed reservation commits with null `accepted_event_id`.
- [ ] **Step 5:** Reuse the alert's fixture detection basis on lifecycle events while retaining the reservation-first global identity and per-alert lock semantics.

---

### Task 9: On-demand EDA endpoints

**Files:** Create EDA SQL/routes and `test_eda.py`.

**Interfaces:** Produce only `/api/eda/summary`, `/api/eda/distributions`, and `/api/eda/correlation`. EDA remains query-time only with no cache, table, or service.

- [ ] **Step 1:** Add failing tests for one or two TALPHA scopes, half-open samples, finite outputs, bounded candidates and bins, distinct correlation fields, empty or zero-variance null correlation, and correlation cursor counts.
- [ ] **Step 2:** Derive EDA telemetry facts from persisted rows and fixture metadata: validation rows, two gaps, >600-second gap threshold, and irregular cadence facts. Do not calculate expected coverage with a five-minute divisor or any fixed source interval.
- [ ] **Step 3:** Use physical inverse-scaled Celsius and RH values. Map scores only to their associated persisted windows. Candidate outliers are deterministic threshold fixtures, not confirmed anomalies or labels.
- [ ] **Step 4:** Keep non-raw aggregation in SQL. No interpolation, resampling, or synthetic bucket is returned. Handle constant distributions with one nonzero-width bin and keep all output finite.

---

### Task 10: Model-evaluation list and single-decoded detail

**Files:** Create evaluation SQL/routes and `test_evaluations.py`.

**Interfaces:** Register `GET /api/model-evaluations` before `GET /api/model-evaluations/{version:path}`. The handler receives the once-decoded path string and never calls another decoder.

- [ ] **Step 1:** Add failing tests for page bounds, exactly seven summaries, the approved version set, detail 404, current validation-track field names, exact list route, empty trailing detail 404, and direct already-decoded slash values.
- [ ] **Step 2:** Order summaries deterministically by the designated fixture order or a documented stable `version ASC` order. Do not represent any track as active, best, selected, production, or deployable.
- [ ] **Step 3:** Return exactly the seven validation-only tracks with their published labels, score key and semantics, thresholds, 86,017 windows, strict validation p99.5 policy, unlabeled status, test-not-evaluated status, and accepted calibration metrics only.
- [ ] **Step 4:** Omit confusion matrices, ROC, precision-recall, F1, accuracy, ranking, and all other unsupported performance or label-dependent structures. Do not invent an artifact creation timestamp.
- [ ] **Step 5:** Reserve percent-encoded Nginx wire-path assertions for Task 15.

---

### Task 11: Liveness, readiness, and system observation

**Files:** Create system SQL/routes and `test_system.py`.

**Interfaces:** Produce only `GET /health`, `GET /ready`, and `GET /api/system/status`.

- [ ] **Step 1:** Add failing tests for health without database access, ready 200 only when DB and revision are ready, database/revision 503 Problem Details, strict no-offset timestamps, two-node telemetry totals, and deferred inference observation.
- [ ] **Step 2:** Keep `/health` process-only. Keep `/ready` limited to API execution, database connectivity, and migration revision. It never checks MQTT, model artifact, or inference.
- [ ] **Step 3:** Make system status an observation snapshot. It reports API and database observations, TALPHA persisted telemetry counts, and `inference-worker` with `unknown` liveness, `not_ready` readiness, and deferred M1 detail.
- [ ] **Step 4:** Do not claim that a runtime-generated status timestamp supplies TALPHA timezone evidence.

---

### Task 12: Assemble the FastAPI application

**Files:** Modify `main.py`; create `test_app.py`; expose completed router objects only.

**Interfaces:** Assemble exactly the 15 existing method/path boundaries. Preserve list-before-detail model-evaluation route registration, strict schemas, and lifespan engine disposal.

- [ ] **Step 1:** Add a failing production route-matrix test for all 15 boundaries.
- [ ] **Step 2:** Register telemetry, inference, alerts, EDA, evaluations, and system routers without CORS, new routes, or response fields outside current contracts.
- [ ] **Step 3:** Assert only TALPHA device IDs and no-offset timestamp serializations traverse the assembled routes.

---

### Task 13: Prepare root/backend Compose, then finalize Nginx and Compose topology

**Dependencies:** The Backend Lane may perform root/backend-only preparation after its own prerequisites are ready. Frontend/Nginx finalization is an integration join and waits for completion and handoff from both lanes.

**Files:** Backend/root-only preparation modifies root Compose, `.env.example`, `.gitignore`, and backend Dockerfile. The integration join may then modify existing `frontend/nginx.conf`. Do not modify `frontend/Dockerfile`; do not edit any file under `frontend/`, including `frontend/nginx.conf`, before the Frontend Lane handoff.

**Interfaces:** Produce private `db`, `migrate`, `seed`, and `api`, plus public `nginx` with only `NGINX_PORT` mapped to the host.

- [ ] **Step 1:** In the Backend Lane, prepare and test the root/backend-only topology for exactly five services, only Nginx with `ports`, no DB host port, and the required backend service dependency chain. Do not edit or claim validation of `frontend/nginx.conf` yet.
- [ ] **Step 2:** In the Backend Lane, configure order `db healthy -> migrate complete -> seed complete -> api healthy -> nginx` and inject all five PostgreSQL variables into migrate, seed, and API.
- [ ] **Step 3:** In the Backend Lane, package only the checked-in backend TALPHA fixture export in the seed image. Assert it contains no sibling-repository mount, symlink, path, runtime read, or build-time import.
- [ ] **Step 4:** At the integration join, after Frontend Lane handoff, update and verify `frontend/nginx.conf`: use `proxy_pass http://api:8000;` without a URI component or trailing slash for `/api/`, `/health`, and `/ready`, so Nginx forwards the raw request URI and Uvicorn performs the sole decoding step.

---

### Task 14: Add isolated real-backend Vitest contract lane

**Depends on:** Integration join: both the Frontend Lane reconciliation handoff and Backend Lane Tasks 1 through 13 final integration are complete. This is a join gate, not a prerequisite for Backend Tasks 1 through 12. Frontend code is outside this backend plan.

**Files:** When the prerequisite is complete, create `frontend/vitest.contract.config.ts` and `frontend/tests/contract/m1-real-backend.contract.ts`; modify only the frontend package script needed to isolate that lane.

**Interfaces:** Consume a completed Nginx stack at `M1_BASE_URL`, existing Zod schemas only, and no MSW server. Existing tests and `frontend/src/main.tsx` remain unchanged.

- [ ] **Step 1:** Gate this lane on `M1_BASE_URL`; it must not be discovered by ordinary frontend unit tests.
- [ ] **Step 2:** Parse all 15 real-backend success and Problem Details boundaries using current Zod schemas.
- [ ] **Step 3:** Update coverage from six sensors to exactly two TALPHA IDs. Test rejection of `n1` through `n6`, strict historical no-offset timestamp strings rather than RFC3339 offsets, bounded fixture records, deterministic score provenance, detection basis, source gaps, and seven evaluation tracks.
- [ ] **Step 4:** Cover defaults and bounds, all four cursor prefixes, half-open telemetry/events/correlation, whole-window inference, command replay, finite values, and single-decoded evaluation versions.

---

### Task 15: Add isolated real-backend Playwright lane

**Depends on:** Verification join: both lane handoffs and Task 13 final integration are complete, plus Task 14's compatibility assumptions. This is a join gate, not a prerequisite for Backend Tasks 1 through 12. Frontend adaptation remains outside this backend plan.

**Files:** When the prerequisite is complete, create `frontend/playwright.real.config.ts`, `frontend/tests/e2e-real/helpers.ts`, and `frontend/tests/e2e-real/m1.spec.ts`; modify only the isolated frontend package script.

**Interfaces:** Consume a clean Nginx stack at `M1_BASE_URL`. Do not start Vite, inject MSW scenarios, modify `frontend/src/main.tsx`, or alter existing Playwright configuration/specifications.

- [ ] **Step 1:** Verify SPA fallback, `/health`, `/ready`, a two-node TALPHA dashboard load, the seeded TALPHA-1 fixture alert, no-offset historical display, and gap rendering.
- [ ] **Step 2:** Exercise direct resolve returning 409 before acknowledgement, then acknowledgement, reload, resolution, and reload with fresh command IDs.
- [ ] **Step 3:** Verify Nginx to Uvicorn single decoding for `release%2F2026`, `release%252F2026`, `release%20candidate`, and `100%25stable`.
- [ ] **Step 4:** Assert visible fixture-only wording does not turn deterministic threshold fixtures into ground truth, runtime inference, or deployment evidence.

---

### Task 16: Deferred verification and delivery review

**Files:** No files are created or modified by this task.

**Interfaces:** Review the artifacts from Tasks 1 to 15 only after implementation is separately authorized. This task produces evidence, not a new runtime interface.

- [ ] **Step 1:** Verify migration idempotence, six-table/two-hypertable scope, `timestamp without time zone` use, TALPHA checks, and absence of retention/compression.
- [ ] **Step 2:** Verify seed transactionality, source-hash metadata, no sibling read, no timestamp shift, exact bounded provenance indices, irregular-cadence gap policy, deterministic fixture scores, one alert, and seven validation-only evaluation tracks.
- [ ] **Step 3:** Verify all backend route, transaction, numeric, readiness, Compose, and Nginx decoding tests.
- [ ] **Step 4:** After both lanes complete their integration join, run isolated real-backend contract and browser lanes with the same `M1_BASE_URL`, then preserve existing frontend lanes unchanged.
- [ ] **Step 5:** Verify scope excludes MQTT, PyTorch runtime, retention, compression, cache, extra services, routes, tables, ports, cross-repository reads, fake metrics, and forbidden legacy or locked-test sources.

## M2 portable-manifest seam

M2 may add private MQTT ingestion and PyTorch inference without changing M1 public routes, Nginx topology, or alert transaction semantics. Before that work, a portable manifest must bundle the schema, feature order and mapping, scaler values and formula, `(0,200)` filter, timestamp and timezone policy, `>600s` gap rule, 30-reading stride-1 windowing, window-end event time, model architecture configuration and checkpoint, selected epoch/arm/channel indices, score formula and key, threshold source/value/comparison, runtime compatibility, and SHA-256 for every artifact.

The active-model pointer remains unset until final locked-test evaluation and model selection exist. M1 validation fixtures cannot supply that pointer.

## Scope and risk

- The largest contract risk is diverging from strict current Zod schemas. Tasks 1, 5, 14, and 16 make those schemas the wire-format test authority.
- The largest data risk is losing TALPHA provenance or turning irregular timestamps into a fabricated cadence. Tasks 3, 4, 6, and 9 retain local timestamps, source indexes, segment boundaries, and the >600-second gap rule.
- The largest transactional risk is alert-command races. Task 8 reserves `command_id` before locking the alert and tests owner-transaction waiting and replay behavior.
- The largest proxy risk is decoding a model version twice. Tasks 10, 13, and 15 retain raw Nginx forwarding and test encoded variants.

## Deferred handoff

This revised TALPHA plan is complete as documentation. This edit does not authorize implementation. After separate authorization, the Frontend Lane and Backend Lane may begin in parallel against the approved, frozen TALPHA contract; Task 13 frontend/Nginx finalization and Tasks 14 through 16 remain join gates requiring both lanes.

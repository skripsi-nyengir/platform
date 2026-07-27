# B02 v3 EDA operations and reproducibility

## Scope and boundary

`/eda` is a B02 v3-only descriptive evidence surface. It is independent of
the platform's classification and forecasting systems. It stores and presents
source, pairing, calendar, distribution, association, and reproducibility
evidence only. Quality flags are candidate evidence, not reference truth.
Association and temporal summaries describe the selected data; they do not
establish direction, cause, intervention effect, or a label for an observation.

There are no scheduled EDA jobs and no administrative HTTP or UI surface.
Operators use the Compose services and the five read/compute operations below.
Historical documents under `docs/superpowers/` are records, not an EDA v3
contract.

## Release identity and provenance

The active B02 v3 release has these fixed identities:

| Field | Value |
| --- | --- |
| device | `b02f3872-39a2-4b6f-a4ec-045a287fde4b` |
| time zone | `Asia/Jakarta` |
| algorithm version | `bivariate_b02f3872_eda_v3+vendor.37565a5341be56e9a0a88d55ce1dbfe6ae25b0fe` |
| configuration hash | `1081a79b8452075df4baf2f88f6ed3094f90286c0e17ee7d666e0b8072ba8452` |
| source SHA-256 | `b8ae739a427681735792f02eea14dd8b7fc53f5265630a7e9a62b846f7b8040f` |
| source manifest SHA-256 | `196178e7424bd2e92268606f0ef33237d2329bdfefd9dce592283c07a697d486` |
| Alembic head | `20260726_0003` |

Only a run with `canonical_release=true` and `period_kind=full_range` is a
canonical published-parity result. Its label is `published v3 release`.
Every daily, weekly, monthly, or custom-range result is labelled
`algorithm-equivalent range computation`. The latter runs the same vendored
algorithm and records source/configuration identity, but it is not a claim of
published full-range parity.

The cache identity is the SHA-256 of canonical JSON for:

```text
(source_sha256, from_ts, to_ts, period_kind, algorithm_version, config_hash)
```

This `logical_key` deliberately excludes the trigger and snapshot UUID.
Published immutable results with all eleven sections are cache hits. A queued
or running job with the same key coalesces with a repeated request.

## Configuration and preflight

Copy the template to a private `.env` and replace every `REPLACE_WITH...` or
`<...>` value. The template has no local absolute source path or usable
credential. The four worker variables are passed to `eda-worker`; its heartbeat
must remain shorter than its lease. `EDA_RAW_SOURCE_PATH` and
`EDA_SOURCE_MANIFEST_PATH` are host paths used only by the `eda-import` bind
mounts. `EDA_SOURCE_MANIFEST_SHA256` must remain the value in the identity
table. The commented algorithm/configuration/head fields in `.env.example` are
audit placeholders only, not runtime inputs.

These non-mutating checks verify the Compose profiles and migration head:

```sh
docker compose config --quiet
docker compose --profile ops config --services
docker compose --profile eda-import config --services
docker compose run --rm --no-deps migrate alembic -c alembic.ini heads
```

The last command prints `20260726_0003 (head)`. The `migrate` service itself
runs `alembic -c alembic.ini upgrade head` before seed/API dependencies.

Confirm the image holds the authoritative release values without mounting the
authority repository into runtime Python:

```sh
docker compose run --rm --no-deps eda-worker python -c "from anomaly_eda import ALGORITHM_VERSION, CONFIG_HASH; print(f'algorithm_version={ALGORITHM_VERSION}'); print(f'config_hash={CONFIG_HASH}')"
```

`eda-worker` uses the Python 3.12 `eda-worker` Dockerfile stage and has a
2 GiB (`2147483648` byte) memory limit. `eda-cli` uses the Python 3.13
`runtime` stage and does not import `anomaly_eda`.

## Canonical raw import and migration

The `eda-import` service is enabled only by the `eda-import` profile. It mounts
the CSV and manifest read-only, invokes `python -m anomaly_backend.eda_importer`,
and deliberately builds from the `eda-worker` stage because the importer needs
the authoritative `anomaly_eda.config.CONFIG_HASH`.

```sh
docker compose --profile eda-import run --rm eda-import
```

On the canonical source, the result is one complete `eda_source_snapshots` row
with configuration hash `1081a79b8452075df4baf2f88f6ed3094f90286c0e17ee7d666e0b8072ba8452`,
source hash `b8ae739a427681735792f02eea14dd8b7fc53f5265630a7e9a62b846f7b8040f`,
and `6,931,792` rows. Repeating the matching import is an idempotent noop.

Snapshot identity fields and completed raw evidence are immutable. The
`eda_reject_immutable_change` trigger rejects snapshot identity updates and
deletes. Do not edit a snapshot to repair a bad hash. Use a fresh database,
correct the source/manifest/configuration, and import again.

## Worker and manual backfill

The `eda-worker` Compose service runs `python -m anomaly_worker.eda_service`.
It must be running to claim jobs; otherwise new jobs remain `queued`.
Start it through the normal deployment lifecycle and inspect the service state:

```sh
docker compose up -d eda-worker
docker compose ps --status running eda-worker
```

The operator-only `eda-cli` is under the `ops` profile and only enqueues
closed precompute periods. Its actual command surface is verified with:

```sh
docker compose --profile ops run --rm --no-deps eda-cli --help
docker compose --profile ops run --rm --no-deps eda-cli backfill --help
```

`backfill` requires `--kind daily|weekly|monthly|all`, `--from`, and `--to`;
`--json` is optional. After a complete canonical import, enqueue the closed
periods with:

```sh
docker compose --profile ops run --rm eda-cli backfill --kind all --from 2025-06-23T00:00:00 --to 2026-07-24T09:02:05 --json
```

Its JSON counters are `cache_hits`, `active_jobs`, `enqueued`, `skipped_open`,
`skipped_outside_source`, and `errors`. It exits `0` when there are no
per-period errors, `1` when `errors` is nonzero, and `2` for invalid
scope/snapshot/database validation. There is no scheduler: run this command
only when an operator chooses to create closed precomputes.

## API and generated OpenAPI

The generated API description is available at [`/openapi.json`](/openapi.json).
The current runtime has exactly these five EDA operations; no older summary,
distribution, or correlation operation is active:

| Operation | Contract |
| --- | --- |
| `GET /api/eda/periods?period_kind=daily|weekly|monthly` | Returns active, fully published periods. `full_range` is not accepted here. |
| `POST /api/eda/compute` | Accepts only a custom B02 range and returns either a cache hit or a job. |
| `GET /api/eda/jobs/{job_id}` | Returns a queued, running, succeeded, or failed job. |
| `GET /api/eda/runs/{run_id}` | Returns a fully published run and metadata for all eleven sections. |
| `GET /api/eda/runs/{run_id}/sections/{section}` | Returns one complete, not-eligible, or failed section directly. |

This source-level OpenAPI check prints those five paths and exits successfully:

```sh
docker compose run --rm --no-deps api python -c "from anomaly_backend.main import app; paths=sorted(path for path in app.openapi()['paths'] if path.startswith('/api/eda/')); print('\\n'.join(paths)); assert len(paths) == 5"
```

For `POST /api/eda/compute`, the strict JSON body requires all of:

```json
{
  "device_id": "b02f3872-39a2-4b6f-a4ec-045a287fde4b",
  "time_zone": "Asia/Jakarta",
  "period_kind": "custom",
  "from": "2026-06-24T00:00:00",
  "to": "2026-07-24T00:00:00"
}
```

It returns `200` with `cache_hit=true` and an immutable run only after all
eleven sections are published. A new request or active-key coalescing returns
`202` with `cache_hit=false` and a job. `404` means an unknown job or a
missing/non-published run or section. `409` means a persisted lifecycle
conflict where a succeeded job lacks its run. `422` is a strict query/body,
range, UUID, cursor, period-kind, or section validation error. `429` applies
only to a distinct custom cache miss when 32 custom jobs are queued/running;
cache hits and active-key coalescing bypass that limit. `503
eda-source-unavailable` means `/periods` or `/compute` cannot select a
complete source snapshot matching the active source, algorithm, and
configuration identity.

## Sections, evidence, and interpretation

Each API run has exactly eleven sections. The UI exposes the following
first-class panel families, some of which are views of one API section.
`not_eligible` is a diagnostic result, not an empty successful payload.

| Panel family and API section | Population and units | Minimum evidence and `not_eligible` reason | Interpretation boundary |
| --- | --- | --- | --- |
| `quality_overview` | Pair/source audit, counts, hashes, flag conservation. | At least one exact pair; `no_exact_pairs`. | Median-resolved duplicate timestamps are not original raw duplicates. |
| `pairing_audit` (`quality_overview`) | Exact-pair, duplicate, exclusion, and cadence audit; counts/seconds. | Same as overview; `no_exact_pairs`. | Pairing is exact timestamp matching, not a nearest-time join. |
| `quality_integrity` (`quality_overview`) | Count conservation, flag overlap, masks, and source transport audit. | Same as overview; `no_exact_pairs`. | Flags are evidence for review, not reference truth. |
| `joint_density` | Raw/screened 120 x 200 histogram over 0-60 degrees C and 0-100 %. | At least one exact pair; `no_exact_pairs`. | Non-finite and out-of-bin values are audited outside the histogram. |
| `univariate` | Per-channel raw/screened histograms and ECDFs; degrees C and %. | At least one exact pair; `no_exact_pairs`. | ECDF denominators use selected finite values. |
| `quality_excerpt` | Up to 2,000 selected flagged records with 1,800-second context. | A selected event; `no_exact_pairs` or `no_selectable_excerpt`. | This is priority-selected context, not a representative sample. |
| `temporal_coverage` | Jakarta hourly/daily/monthly bins, exposure seconds, counts, uncapped fractions. | Positive accepted delta and an exposed bin; `no_positive_deltas` or `no_exposed_calendar_bins`. | Custom-range edge bins are censored. |
| `weekday_hour_coverage` (`temporal_coverage`) | Jakarta weekday-hour view of coverage; fractions and counts. | Same as temporal coverage. | Calendar labels are Asia/Jakarta, not browser-local time. |
| `temporal_distribution` | Per-bin median, Q1, Q3, MAD in degrees C/% and cadence. | Positive deltas and median cadence exactly 6 seconds; `no_positive_deltas` or `insufficient_representative_cadence`. | Direction badges are descriptive comparisons, not tests. |
| `relationships` / association | Finite raw/screened Pearson and Spearman coefficients; unitless. | At least 30 nonconstant finite pairs per view; `no_exact_pairs` or `insufficient_nonconstant_pairs`. | Coefficients describe association only. |
| `rolling_correlation` (`relationships`) | Six rolling Pearson variants; coefficient, seconds, epoch-second endpoints. | At least one eligible primary window with 30 pairs, 80% coverage, and nonzero variance; `insufficient_rolling_windows`. | Overlapping windows are not independent observations. |
| `stationarity` | Screened 80%-coverage hourly medians, ACF/PACF, spectrum, STL; coefficients and degrees C/%. | One 336-hour sensitivity segment; `insufficient_stationarity_sensitivity_tier`. | Internal diagnostic tests are not published gates. |
| `autocorrelation` (`stationarity`) | ACF/PACF by lag; unitless. | Same stationarity segment. | It describes temporal repetition in eligible hourly medians only. |
| `spectrum` (`stationarity`) | Periodogram frequencies and power. | Same stationarity segment. | Missing power remains unavailable, not zero. |
| `stl` (`stationarity`) | Trend, seasonal, and residual components in degrees C/%. | Same stationarity segment. | Components are descriptive decompositions of the selected segment. |
| `change_points` | Dense screened daily medians, robust scales, 7/14/28-day confirmations; degrees C/%, unitless effects, day ordinals. | A dense run of at least 90 days; `insufficient_daily_medians`. | Output is a regime-change candidate, not a label for any reading. |
| `uncertainty` | Seeded 2,000-replicate paired moving-block Pearson/Spearman intervals; unitless. | Primary 14-day block with a run at least 14 days and 30 nonconstant daily pairs; `block_longer_than_run` or `insufficient_dense_daily_pairs`. | `robust` means sign agreement across block lengths, not a significance conclusion. |
| `audit_metadata` | Dataset/release/dependency/seed/manifest provenance. | Staged after valid source identity; contract reason `source_identity_unavailable`. | Provenance evidence, not a statistic. |

## Canonical proof

Run canonical proof only in its isolated test database. It mounts the source
authority read-only; it does not make that repository a runtime Python import.

```sh
docker compose run --rm -v "${AUTHORITY_DIR:?set authority repository}:/authority:ro" -e EDA_CANONICAL_RAW_CSV=/authority/data/raw/bivariate_b02f3872_v1/sensor_data_long.csv eda-worker python -m pytest -q -m canonical tests/test_eda_authority_parity.py tests/test_eda_integration.py
```

The isolated proof verifies source import, full-range compute, all section
hashes, API reads, and idempotent reimport. It is intentionally not a routine
operator command. See `.omo/evidence/task-21-canonical-integration.txt` for
the recorded `2 passed` execution and timing.

## Troubleshooting and recovery

| Symptom | Check and recovery |
| --- | --- |
| `eda-source-unavailable` or hash drift | Compare source SHA, manifest SHA, algorithm version, and configuration hash against the identity table. Rebuild the EDA image if the importer cannot equal the authoritative configuration hash. Never calculate a substitute hash by hand. |
| Manifest/source mismatch | Confirm both read-only mount paths and the fixed manifest digest. A changed CSV or manifest is a different snapshot identity; use a fresh database for a corrected import. |
| Invalid archive | The legacy `import` service consumes `B02_RAW_ARCHIVE_PATH`; `eda-import` consumes the CSV plus manifest instead. Do not substitute an archive for the EDA source inputs. |
| Missing precomputes | A `200` period list can be empty when no matching published periods exist. Import first, then use the operator backfill command for closed periods. A `503` means no matching complete source snapshot exists. |
| Failed or transient job | Read the job resource. Transient worker/database failures release work back to `queued` until the three-attempt limit; deterministic/timeout failures become terminal. Correct the cause, then request a new logical key or requeue through the intended operator flow. |
| Stale lease | Keep `eda-worker` running. Claiming uses an expiring lease and fenced heartbeat; an expired claim can be reclaimed. Do not edit lease columns manually. |
| Cache miss after release upgrade | A source, algorithm, or configuration change changes `logical_key` by design. Import a matching complete snapshot, then backfill or request the required range. Old immutable runs remain retrievable by ID. |
| Canonical parity failure | Run the isolated canonical proof, compare the fixed counts and all source identities, and use the Python 3.12 `eda-worker` image. Do not interpret a custom-range result as a substitute full-range proof. |
| Bad completed snapshot | `eda_source_snapshots` is immutable. Do not update or delete it in place. Reset only a fresh, disposable database and import the corrected source there; never use a production/demo reset as a repair step. |

## Verification record

Task 23 command/output evidence is recorded in
`.omo/evidence/task-23-operations-docs.txt`. The forbidden-content guard is
recorded in `.omo/evidence/task-23-operations-docs-error.txt`.

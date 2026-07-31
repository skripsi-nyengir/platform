import asyncio
import hashlib
from importlib import resources
from typing import cast

from sqlalchemy import func, select

from anomaly_backend import tables
from anomaly_backend.config import Settings
from anomaly_backend.db import create_database_engine
from anomaly_backend.pilot import (
    NORMALIZED_PATH,
    PILOT_DISCLAIMER,
    SOURCE_COMMIT,
    STEP10_PATH,
    STEP10_SHA256,
    STEP8_PATH,
    STEP8_SHA256,
    load_tracked_normalized_snapshot,
    normalized_pilot_snapshot,
)
from anomaly_backend.seed import seed_database


PUBLIC_MODEL_KEYS = {
    "ewma",
    "pca",
    "wsn-dense-ae",
    "lstm-ae",
    "usad",
    "cfc-autoencoder",
    "mtad-gat",
}
PUBLIC_DEVICE_ID = "b02f3872-ruang-produksi"


def _fixture_bytes(path: str) -> bytes:
    return resources.files("anomaly_backend").joinpath(path).read_bytes()


def test_pilot_source_files_match_pinned_hashes() -> None:
    assert hashlib.sha256(_fixture_bytes(STEP8_PATH)).hexdigest() == STEP8_SHA256
    assert (
        hashlib.sha256(_fixture_bytes(STEP10_PATH)).hexdigest()
        == STEP10_SHA256
    )


def test_normalized_pilot_is_derived_from_pinned_sources() -> None:
    normalized = normalized_pilot_snapshot()
    models = cast(list[dict[str, object]], normalized["models"])

    assert load_tracked_normalized_snapshot() == normalized
    assert resources.files("anomaly_backend").joinpath(NORMALIZED_PATH).is_file()
    assert normalized["source_commit"] == SOURCE_COMMIT
    assert normalized["disclaimer"] == PILOT_DISCLAIMER
    assert normalized["test_observed"] is True
    assert normalized["independent_final"] is False
    assert {
        model["model_key"] for model in models
    } == PUBLIC_MODEL_KEYS
    assert all(
        model["stuck_event_hit_rate"] == 0.0
        for model in models
    )


def test_seed_keeps_preview_versions_as_unselectable_history() -> None:
    async def verify() -> None:
        engine = create_database_engine(Settings.from_environ())
        try:
            async with engine.connect() as connection:
                await seed_database(connection)
                public_families = set(
                    await connection.scalars(
                        select(tables.model_families.c.model_key).where(
                            tables.model_families.c.is_public
                        )
                    )
                )
                versions = (
                    await connection.execute(
                        select(
                            tables.model_versions.c.version,
                            tables.model_versions.c.runtime_kind,
                            tables.model_versions.c.is_selectable,
                            tables.model_versions.c.contract_status,
                            tables.model_versions.c.model_manifest_sha256,
                            tables.model_versions.c.checkpoint_sha256,
                            tables.model_versions.c.scaler_manifest_sha256,
                            tables.model_versions.c.scaler_sha256,
                            tables.model_versions.c.threshold,
                            tables.model_versions.c.threshold_policy,
                        )
                        .join(
                            tables.model_families,
                            tables.model_families.c.model_key
                            == tables.model_versions.c.model_key,
                        )
                        .where(tables.model_families.c.is_public)
                    )
                ).mappings().all()
                pilots = (
                    await connection.execute(
                        select(
                            tables.model_evaluations.c.model_key,
                            tables.model_evaluations.c.report_source,
                            tables.model_evaluations.c.test_observed,
                            tables.model_evaluations.c.independent_final,
                            tables.model_evaluations.c.source_commit,
                            tables.model_evaluations.c.source_sha256,
                        ).where(tables.model_evaluations.c.is_public)
                    )
                ).mappings().all()
                selection = (
                    await connection.execute(
                        select(tables.active_model_selections).where(
                            tables.active_model_selections.c.device_id
                            == PUBLIC_DEVICE_ID
                        )
                    )
                ).mappings().one_or_none()
        finally:
            await engine.dispose()

        assert public_families == PUBLIC_MODEL_KEYS
        assert {row["version"] for row in versions} == {
            f"preview-{key}-v1" for key in PUBLIC_MODEL_KEYS
        }
        assert all(row["runtime_kind"] == "preview_simulator" for row in versions)
        assert all(row["is_selectable"] is False for row in versions)
        assert all(row["contract_status"] == "legacy_30" for row in versions)
        assert all(
            row[hash_column] is None
            for row in versions
            for hash_column in (
                "model_manifest_sha256",
                "checkpoint_sha256",
                "scaler_manifest_sha256",
                "scaler_sha256",
            )
        )
        assert all(row["threshold"] == 1.0 for row in versions)
        assert all(
            row["threshold_policy"]["comparator"] == ">" for row in versions
        )
        assert {row["model_key"] for row in pilots} == PUBLIC_MODEL_KEYS
        assert all(
            row["report_source"] == "reported_dandy_pilot"
            and row["test_observed"] is True
            and row["independent_final"] is False
            and row["source_commit"] == SOURCE_COMMIT
            and row["source_sha256"] in {STEP8_SHA256, STEP10_SHA256}
            for row in pilots
        )
        assert selection is None

    asyncio.run(verify())


def test_seed_is_idempotent_for_preview_catalog() -> None:
    async def verify() -> None:
        engine = create_database_engine(Settings.from_environ())
        try:
            async with engine.connect() as connection:
                await seed_database(connection)
                before = {
                    "families": await connection.scalar(
                        select(func.count()).select_from(tables.model_families)
                    ),
                    "versions": await connection.scalar(
                        select(func.count()).select_from(tables.model_versions)
                    ),
                    "activations": await connection.scalar(
                        select(func.count()).select_from(tables.model_activations)
                    ),
                    "evaluations": await connection.scalar(
                        select(func.count()).select_from(
                            tables.model_evaluations
                        )
                    ),
                }
                await connection.rollback()
                await seed_database(connection)
                after = {
                    "families": await connection.scalar(
                        select(func.count()).select_from(tables.model_families)
                    ),
                    "versions": await connection.scalar(
                        select(func.count()).select_from(tables.model_versions)
                    ),
                    "activations": await connection.scalar(
                        select(func.count()).select_from(tables.model_activations)
                    ),
                    "evaluations": await connection.scalar(
                        select(func.count()).select_from(
                            tables.model_evaluations
                        )
                    ),
                }
        finally:
            await engine.dispose()

        assert after == before

    asyncio.run(verify())


def test_seed_keeps_legacy_registry_internal_and_nonselectable() -> None:
    async def verify() -> list[dict[str, object]]:
        engine = create_database_engine(Settings.from_environ())
        try:
            async with engine.connect() as connection:
                await seed_database(connection)
                return [
                    dict(row)
                    for row in (
                        await connection.execute(
                            select(
                                tables.model_versions.c.version,
                                tables.model_versions.c.runtime_kind,
                                tables.model_versions.c.is_selectable,
                                tables.model_families.c.is_public,
                            )
                            .join(
                                tables.model_families,
                                tables.model_families.c.model_key
                                == tables.model_versions.c.model_key,
                            )
                            .where(
                                tables.model_versions.c.version.in_(
                                    (
                                        "conv1d-arm-b-talpha-1-validation-fixture",
                                        "conv1d-arm-b-talpha-2-validation-fixture",
                                    )
                                )
                            )
                            .order_by(tables.model_versions.c.version)
                        )
                    ).mappings()
                ]
        finally:
            await engine.dispose()

    rows = asyncio.run(verify())
    assert [row["version"] for row in rows] == [
        "conv1d-arm-b-talpha-1-validation-fixture",
        "conv1d-arm-b-talpha-2-validation-fixture",
    ]
    assert all(
        row["runtime_kind"] == "legacy_fixture"
        and row["is_selectable"] is False
        and row["is_public"] is False
        for row in rows
    )

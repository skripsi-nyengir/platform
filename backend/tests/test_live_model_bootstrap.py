from __future__ import annotations

import asyncio
from dataclasses import replace
import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
from collections.abc import Iterator
from typing import cast
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend import tables
from anomaly_backend.config import Settings
from anomaly_backend.db import create_database_engine
from anomaly_backend.live_model_bootstrap import (
    LiveModelBundleError,
    bootstrap_live_model,
)
from anomaly_worker import artifact_scorer
from anomaly_worker.artifact_scorer import ArtifactDescriptor, ArtifactScorer
from tests.live_bundle_fixture import (
    canonical_bytes,
    rewrite_json,
    sha256,
    write_bundle,
)


@pytest.fixture(scope="module")
def clean_settings() -> Iterator[Settings]:
    base = Settings.from_environ()
    database = f"anomaly_detection_task5_{uuid4().hex[:12]}"
    with psycopg.connect(
        host=base.postgres_host,
        port=base.postgres_port,
        dbname="postgres",
        user=base.postgres_user,
        password=base.postgres_password,
        autocommit=True,
    ) as connection:
        connection.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database))
        )
    environment = os.environ.copy()
    environment["POSTGRES_DB"] = database
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=Path(__file__).parents[1],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    settings = replace(base, postgres_db=database)
    try:
        yield settings
    finally:
        with psycopg.connect(
            host=base.postgres_host,
            port=base.postgres_port,
            dbname="postgres",
            user=base.postgres_user,
            password=base.postgres_password,
            autocommit=True,
        ) as connection:
            connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (database,),
            )
            connection.execute(
                sql.SQL("DROP DATABASE {}").format(sql.Identifier(database))
            )


def _allow_cpu_load(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(artifact_scorer.torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(
        artifact_scorer,
        "_cuda_device",
        lambda: artifact_scorer.torch.device("cpu"),
        raising=False,
    )


def _configure_bundle(
    monkeypatch: pytest.MonkeyPatch, root: Path, bundle_id: str
) -> None:
    monkeypatch.setenv("MODEL_ARTIFACTS_PATH", str(root))
    monkeypatch.setenv("LIVE_MODEL_BUNDLE_ID", bundle_id)
    monkeypatch.delenv("MODEL_ARTIFACTS_DIR", raising=False)


def test_clean_database_bootstrap_is_atomic_and_idempotent(
    clean_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_id, files = write_bundle(tmp_path)
    _configure_bundle(monkeypatch, tmp_path, bundle_id)
    _allow_cpu_load(monkeypatch)

    async def run() -> None:
        engine = create_database_engine(clean_settings)
        try:
            async with engine.connect() as connection:
                first = await bootstrap_live_model(connection)
                second = await bootstrap_live_model(connection)
                assert first.model_pair_id == second.model_pair_id
                assert first.activation_id == second.activation_id
                assert first.activated
                assert second.idempotent

                selection = (
                    (
                        await connection.execute(
                            select(
                                tables.live_model_selections.c.model_pair_id,
                                tables.live_model_selections.c.activation_id,
                                tables.live_model_pairs.c.model_manifest_sha256,
                                tables.live_model_pairs.c.checkpoint_sha256,
                                tables.live_model_pairs.c.scaler_manifest_sha256,
                                tables.live_model_pairs.c.scaler_sha256,
                                tables.model_versions.c.model_key,
                                tables.model_versions.c.manifest_sha256,
                                tables.model_versions.c.source_config,
                            )
                            .join(
                                tables.live_model_pairs,
                                tables.live_model_pairs.c.model_pair_id
                                == tables.live_model_selections.c.model_pair_id,
                            )
                            .join(
                                tables.model_versions,
                                tables.model_versions.c.version
                                == tables.live_model_pairs.c.model_version,
                            )
                        )
                    )
                    .mappings()
                    .one()
                )
                expected_hashes = {
                    "model_manifest_sha256": sha256(files["model_manifest"]),
                    "checkpoint_sha256": sha256(files["checkpoint"]),
                    "scaler_manifest_sha256": sha256(files["scaler_manifest"]),
                    "scaler_sha256": cast(str, files["scaler"]["scaler_sha256"]),
                }
                assert {
                    key: selection[key] for key in expected_hashes
                } == expected_hashes
                assert (
                    selection["manifest_sha256"]
                    == expected_hashes["model_manifest_sha256"]
                )
                source_config = json.loads(selection["source_config"])
                assert source_config["hashes"] == expected_hashes
                assert len(set(expected_hashes.values())) == 4
                corpus_id = cast(str, source_config["snapshot_corpus_id"])
                corpus = (
                    (
                        await connection.execute(
                            select(tables.corpora).where(
                                tables.corpora.c.corpus_id == corpus_id
                            )
                        )
                    )
                    .mappings()
                    .one()
                )
                snapshot = (
                    (
                        await connection.execute(
                            select(tables.preprocessing_snapshots).where(
                                tables.preprocessing_snapshots.c.corpus_id == corpus_id
                            )
                        )
                    )
                    .mappings()
                    .one()
                )
                assert corpus["filter_config"]["artifact_owned"] is True
                assert corpus["archive_sha256"] == expected_hashes["scaler_manifest_sha256"]
                assert snapshot["channels"] == [
                    "temperature_c",
                    "relative_humidity_pct",
                ]
                assert snapshot["scaler"] == files["scaler"]
                assert (
                    await connection.scalar(
                        select(func.count())
                        .select_from(tables.model_families)
                        .where(
                            tables.model_families.c.model_key
                            == selection["model_key"]
                        )
                    )
                    == 1
                )
                assert (
                    await connection.scalar(
                        select(func.count())
                        .select_from(tables.model_versions)
                        .where(
                            tables.model_versions.c.version == first.model_version
                        )
                    )
                    == 1
                )
                assert (
                    await connection.scalar(
                        select(func.count())
                        .select_from(tables.live_model_pairs)
                        .where(
                            tables.live_model_pairs.c.model_version
                            == first.model_version
                        )
                    )
                    == 1
                )
                assert (
                    await connection.scalar(
                        select(func.count())
                        .select_from(tables.live_model_selections)
                        .where(
                            tables.live_model_selections.c.model_pair_id
                            == first.model_pair_id
                        )
                    )
                    == 1
                )
                assert (
                    await connection.scalar(
                        select(func.count())
                        .select_from(tables.live_model_activation_requests)
                        .where(
                            tables.live_model_activation_requests.c.model_pair_id
                            == first.model_pair_id
                        )
                    )
                    == 1
                )
                assert (
                    await connection.scalar(
                        select(func.count())
                        .select_from(tables.live_model_activations)
                        .where(
                            tables.live_model_activations.c.model_pair_id
                            == first.model_pair_id
                        )
                    )
                    == 1
                )
                assert (
                    await connection.scalar(
                        select(func.count())
                        .select_from(tables.active_model_selections)
                        .where(
                            tables.active_model_selections.c.model_version
                            == first.model_version
                        )
                    )
                    == 0
                )
        finally:
            await engine.dispose()

    asyncio.run(run())

    source = inspect.getsource(sys.modules[bootstrap_live_model.__module__])
    assert "anomaly_backend.seed" not in source
    assert "sim_import" not in source
    assert "PreviewSimulatorScorer" not in source
    assert "MODEL_ARTIFACTS_DIR" not in source


@pytest.mark.parametrize(
    ("target", "field", "value", "message"),
    [
        ("scaler", "channels", ["rh", "suhu"], "scaler channels"),
        ("scaler", "minimum", [20.0], "minimum"),
        ("scaler", "minimum", [float("nan"), 40.0], "finite"),
        ("scaler", "maximum", [20.0, 39.0], "greater"),
        ("scaler", "fit_split", "", "fit_split"),
        ("scaler", "source", {}, "source"),
        ("scaler", "scaler_sha256", "0" * 64, "canonical"),
        ("model", "manifest_version", 1.0, "manifest_version"),
        ("model", "channels", ["temperature_c", "relative_humidity_pct"], "channels"),
        ("model", "schema_version", "legacy", "schema_version"),
        ("model", "window_size", 10.0, "window_size"),
        ("model", "window_size", 30, "window_size"),
        ("model", "stride", 1.0, "stride"),
        ("model", "stride", 2, "stride"),
        ("model", "temporal_semantics", "next_target", "temporal"),
        ("model", "threshold", 0.0, "positive"),
        ("model", "threshold", float("inf"), "threshold"),
        ("model", "threshold_policy", {"comparison": ">"}, "policy"),
        (
            "model",
            "threshold_policy",
            {"comparison": ">", "fit_split": "holdout", "name": "invalid"},
            "policy fit_split",
        ),
        ("model", "threshold_policy", {"comparison": ">="}, "policy"),
    ],
)
def test_descriptor_rejects_malformed_contracts(
    tmp_path: Path,
    target: str,
    field: str,
    value: object,
    message: str,
) -> None:
    bundle_id, files = write_bundle(tmp_path)
    payload = dict(files["scaler"] if target == "scaler" else files["model"])
    payload[field] = value
    manifest = (
        files["scaler_manifest"] if target == "scaler" else files["model_manifest"]
    )
    rewrite_json(manifest, payload)
    if target == "scaler":
        model = dict(files["model"])
        model["scaler_manifest_sha256"] = sha256(files["scaler_manifest"])
        rewrite_json(files["model_manifest"], model)
    with pytest.raises(LiveModelBundleError, match=message):
        ArtifactDescriptor.load(tmp_path, bundle_id)


def test_descriptor_rejects_unknown_scaler_fit_split(tmp_path: Path) -> None:
    bundle_id, files = write_bundle(tmp_path)
    scaler = dict(files["scaler"])
    scaler["fit_split"] = "holdout"
    scaler.pop("scaler_sha256")
    scaler["scaler_sha256"] = hashlib.sha256(canonical_bytes(scaler)).hexdigest()
    rewrite_json(files["scaler_manifest"], scaler)
    model = dict(files["model"])
    model["scaler_manifest_sha256"] = sha256(files["scaler_manifest"])
    rewrite_json(files["model_manifest"], model)

    with pytest.raises(LiveModelBundleError, match="fit_split"):
        ArtifactDescriptor.load(tmp_path, bundle_id)


@pytest.mark.parametrize("target", ["model", "scaler"])
def test_descriptor_rejects_unknown_manifest_fields(
    tmp_path: Path, target: str
) -> None:
    bundle_id, files = write_bundle(tmp_path)
    payload = dict(files[target])
    payload["unexpected"] = True
    manifest = (
        files["model_manifest"] if target == "model" else files["scaler_manifest"]
    )
    if target == "scaler":
        payload.pop("scaler_sha256")
        payload["scaler_sha256"] = hashlib.sha256(canonical_bytes(payload)).hexdigest()
    rewrite_json(manifest, payload)
    if target == "scaler":
        model = dict(files["model"])
        model["scaler_manifest_sha256"] = sha256(manifest)
        rewrite_json(files["model_manifest"], model)

    with pytest.raises(LiveModelBundleError, match="schema"):
        ArtifactDescriptor.load(tmp_path, bundle_id)


@pytest.mark.parametrize("target", ["model", "scaler"])
def test_descriptor_rejects_duplicate_json_keys(tmp_path: Path, target: str) -> None:
    bundle_id, files = write_bundle(tmp_path)
    manifest = (
        files["model_manifest"] if target == "model" else files["scaler_manifest"]
    )
    duplicate = (
        f',"bundle_id":"{bundle_id}"}}'.encode()
        if target == "model"
        else b',"manifest_version":1}'
    )
    manifest.write_bytes(manifest.read_bytes()[:-1] + duplicate)
    if target == "scaler":
        model = dict(files["model"])
        model["scaler_manifest_sha256"] = sha256(manifest)
        rewrite_json(files["model_manifest"], model)

    with pytest.raises(LiveModelBundleError, match="duplicate"):
        ArtifactDescriptor.load(tmp_path, bundle_id)


@pytest.mark.parametrize("sidecar", ["model_manifest", "scaler_manifest"])
def test_descriptor_rejects_missing_and_malformed_sidecars(
    tmp_path: Path, sidecar: str
) -> None:
    bundle_id, files = write_bundle(tmp_path)
    files[sidecar].unlink()
    with pytest.raises(LiveModelBundleError, match="exactly one"):
        ArtifactDescriptor.load(tmp_path, bundle_id)

    root = tmp_path / "malformed"
    bundle_id, files = write_bundle(root)
    files[sidecar].write_text("{not-json")
    with pytest.raises(LiveModelBundleError, match="JSON"):
        ArtifactDescriptor.load(root, bundle_id)


def test_descriptor_rejects_ambiguous_sidecars_and_checkpoints(tmp_path: Path) -> None:
    bundle_id, files = write_bundle(tmp_path / "sidecars")
    (files["bundle"] / "model-manifest-v2.json").write_bytes(
        files["model_manifest"].read_bytes()
    )
    with pytest.raises(LiveModelBundleError, match="exactly one"):
        ArtifactDescriptor.load(tmp_path / "sidecars", bundle_id)

    bundle_id, files = write_bundle(tmp_path / "checkpoints")
    (files["bundle"] / "other.pt").write_bytes(files["checkpoint"].read_bytes())
    with pytest.raises(LiveModelBundleError, match="exactly one checkpoint"):
        ArtifactDescriptor.load(tmp_path / "checkpoints", bundle_id)


def test_descriptor_rejects_external_sidecar_symlink(tmp_path: Path) -> None:
    bundle_id, files = write_bundle(tmp_path / "artifacts")
    external_manifest = tmp_path / "external-model-manifest.json"
    files["model_manifest"].replace(external_manifest)
    files["model_manifest"].symlink_to(external_manifest)

    with pytest.raises(LiveModelBundleError, match="selected bundle"):
        ArtifactDescriptor.load(tmp_path / "artifacts", bundle_id)


def test_descriptor_rejects_non_numeric_manifest_filename(tmp_path: Path) -> None:
    bundle_id, files = write_bundle(tmp_path)
    files["model_manifest"].rename(
        files["bundle"] / "model-manifest-vbanana.json"
    )

    with pytest.raises(LiveModelBundleError, match="manifest_version"):
        ArtifactDescriptor.load(tmp_path, bundle_id)


def test_descriptor_verifies_checkpoint_and_scaler_manifest_independently(
    tmp_path: Path,
) -> None:
    bundle_id, files = write_bundle(tmp_path)
    files["checkpoint"].write_bytes(files["checkpoint"].read_bytes() + b"changed")
    with pytest.raises(LiveModelBundleError, match="checkpoint SHA-256"):
        ArtifactDescriptor.load(tmp_path, bundle_id)

    root = tmp_path / "scaler-change"
    bundle_id, files = write_bundle(root)
    scaler = dict(files["scaler"])
    scaler["minimum"] = [19.0, 40.0]
    scaler.pop("scaler_sha256")
    scaler["scaler_sha256"] = hashlib.sha256(canonical_bytes(scaler)).hexdigest()
    rewrite_json(files["scaler_manifest"], scaler)
    with pytest.raises(LiveModelBundleError, match="scaler manifest SHA-256"):
        ArtifactDescriptor.load(root, bundle_id)


def test_descriptor_requires_selected_bundle_and_blocks_path_escape(
    tmp_path: Path,
) -> None:
    with pytest.raises(LiveModelBundleError, match="LIVE_MODEL_BUNDLE_ID"):
        ArtifactDescriptor.from_environ({"MODEL_ARTIFACTS_PATH": str(tmp_path)})
    with pytest.raises(LiveModelBundleError, match="escape"):
        ArtifactDescriptor.load(tmp_path, "../outside")


def test_artifact_scorer_requires_cuda_and_loadable_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle_id, _ = write_bundle(tmp_path)
    descriptor = ArtifactDescriptor.load(tmp_path, bundle_id)
    monkeypatch.setattr(artifact_scorer.torch.cuda, "is_available", lambda: False)
    with pytest.raises(LiveModelBundleError, match="CUDA"):
        ArtifactScorer(descriptor)

    _allow_cpu_load(monkeypatch)
    assert ArtifactScorer(descriptor).model_version == descriptor.model_version


def test_artifact_scorer_revalidates_checkpoint_after_descriptor_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle_id, files = write_bundle(tmp_path)
    descriptor = ArtifactDescriptor.load(tmp_path, bundle_id)
    files["checkpoint"].write_bytes(files["checkpoint"].read_bytes() + b"changed")
    _allow_cpu_load(monkeypatch)

    with pytest.raises(LiveModelBundleError, match="checkpoint SHA-256"):
        ArtifactScorer(descriptor)


def test_registration_conflict_rolls_back_partial_artifact_rows(
    clean_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version = f"artifact-lstm-live-{uuid4().hex}"
    first_id, _ = write_bundle(tmp_path / "first", model_version=version)
    second_id, _ = write_bundle(tmp_path / "second", model_version=version)
    _allow_cpu_load(monkeypatch)

    async def run() -> None:
        engine = create_database_engine(clean_settings)
        try:
            async with engine.connect() as connection:
                _configure_bundle(monkeypatch, tmp_path / "first", first_id)
                await bootstrap_live_model(connection)
                before = await connection.scalar(
                    select(func.count()).select_from(tables.corpora)
                )
                await connection.rollback()

                _configure_bundle(monkeypatch, tmp_path / "second", second_id)
                with pytest.raises(ValueError, match="artifact model version"):
                    await bootstrap_live_model(connection)
                after = await connection.scalar(
                    select(func.count()).select_from(tables.corpora)
                )
                assert after == before
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_registration_rejects_conflicting_model_family_without_partial_rows(
    clean_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_id, _ = write_bundle(tmp_path)
    _configure_bundle(monkeypatch, tmp_path, bundle_id)
    _allow_cpu_load(monkeypatch)
    model_key = "live-artifact-lstm-ae"
    conflicting_family = {
        "model_key": model_key,
        "display_name": "conflicting-family",
        "is_public": True,
    }

    async def counts(connection: AsyncConnection) -> tuple[int, ...]:
        values: list[int] = []
        for table in (
            tables.corpora,
            tables.preprocessing_snapshots,
            tables.model_versions,
            tables.live_model_pairs,
        ):
            count = await connection.scalar(select(func.count()).select_from(table))
            values.append(int(count or 0))
        return tuple(values)

    async def run() -> None:
        engine = create_database_engine(clean_settings)
        try:
            async with engine.connect() as connection:
                async with connection.begin():
                    await connection.execute(
                        pg_insert(tables.model_families)
                        .values(**conflicting_family)
                        .on_conflict_do_update(
                            index_elements=["model_key"],
                            set_={
                                "display_name": conflicting_family["display_name"],
                                "is_public": conflicting_family["is_public"],
                            },
                        )
                    )
                    before = await counts(connection)

                with pytest.raises(ValueError, match="artifact model family"):
                    await bootstrap_live_model(connection)

                assert await counts(connection) == before
                family = (
                    (
                        await connection.execute(
                            select(tables.model_families).where(
                                tables.model_families.c.model_key == model_key
                            )
                        )
                    )
                    .mappings()
                    .one()
                )
                assert {
                    key: family[key] for key in conflicting_family
                } == conflicting_family
        finally:
            await engine.dispose()

    asyncio.run(run())

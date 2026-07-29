import asyncio
from importlib import resources
import os
from pathlib import Path
import tomllib
from unittest.mock import patch

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncEngine

from anomaly_backend.config import Settings
from anomaly_backend.db import (
    create_database_engine,
    current_migration_revision,
    database_is_healthy,
)
from anomaly_backend.tables import metadata


DATABASE_ENV = {
    "POSTGRES_HOST": "db",
    "POSTGRES_PORT": "5432",
    "POSTGRES_DB": "anomaly_detection",
    "POSTGRES_USER": "anomaly",
    "POSTGRES_PASSWORD": "anomaly-dev-only",
}


def _compose_services(compose: str) -> dict[str, str]:
    services: dict[str, str] = {}
    current_name: str | None = None
    current_lines: list[str] = []

    for line in compose.splitlines()[1:]:
        if line and not line.startswith(" "):
            break
        if line.startswith("  ") and not line.startswith("    ") and line.endswith(":"):
            if current_name is not None:
                services[current_name] = "\n".join(current_lines)
            current_name = line[2:-1]
            current_lines = []
        elif current_name is not None:
            current_lines.append(line)

    if current_name is not None:
        services[current_name] = "\n".join(current_lines)
    return services


def _environment_keys(service: str) -> set[str]:
    lines = service.splitlines()
    start = lines.index("    environment:")
    keys: set[str] = set()
    for line in lines[start + 1 :]:
        if line.startswith("      "):
            keys.add(line.strip().partition(":")[0])
        elif line:
            break
    return keys


def test_settings_read_only_the_five_postgres_variables() -> None:
    with patch.dict(os.environ, {**DATABASE_ENV, "DATABASE_URL": "ignored"}, clear=True):
        settings = Settings.from_environ()

    assert settings == Settings(
        postgres_host="db",
        postgres_port=5432,
        postgres_db="anomaly_detection",
        postgres_user="anomaly",
        postgres_password="anomaly-dev-only",
    )
    assert settings.async_database_url.drivername == "postgresql+psycopg"
    assert not hasattr(settings, "sync_database_url")


def test_settings_require_every_postgres_variable() -> None:
    for missing in DATABASE_ENV:
        values = {key: value for key, value in DATABASE_ENV.items() if key != missing}
        with patch.dict(os.environ, values, clear=True):
            try:
                _ = Settings.from_environ()
            except KeyError as error:
                assert error.args == (missing,)
            else:
                raise AssertionError(f"expected missing {missing} to fail")


def test_database_engine_is_async_core_owned() -> None:
    engine = create_database_engine(
        Settings(
            postgres_host="db",
            postgres_port=5432,
            postgres_db="anomaly_detection",
            postgres_user="anomaly",
            postgres_password="anomaly-dev-only",
        )
    )

    assert isinstance(engine, AsyncEngine)
    assert isinstance(metadata, MetaData)
    assert set(metadata.tables) == {
        "active_model_selections",
        "alert_events",
        "alert_commands",
        "alerts",
        "corpora",
        "devices",
        "eda_jobs",
        "eda_raw_readings",
        "eda_result_sections",
        "eda_runs",
        "eda_source_snapshots",
        "inference_results",
        "injection_events",
        "model_evaluations",
        "model_activations",
        "model_families",
        "model_versions",
        "preprocessing_snapshots",
        "published_corpora",
        "replay_commands",
        "replay_episode_checkpoints",
        "replay_episode_staging",
        "replay_jobs",
        "replay_result_staging",
        "telemetry",
        "worker_heartbeats",
    }
    assert engine.url.drivername == "postgresql+psycopg"
    asyncio.run(engine.dispose())


def test_database_health_and_revision_use_injected_connection() -> None:
    async def check() -> None:
        settings = Settings.from_environ()
        engine = create_database_engine(settings)
        try:
            async with engine.connect() as connection:
                assert await database_is_healthy(connection)
                assert (
                    await current_migration_revision(connection)
                    == "20260729_0004"
                )
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_compose_defines_expected_services_and_public_nginx() -> None:
    project_root = Path(os.environ["PROJECT_ROOT"])
    compose = (project_root / "compose.yaml").read_text(encoding="utf-8")
    services = _compose_services(compose)

    assert set(services) == {
        "db",
        "migrate",
        "seed",
        "api",
        "worker",
        "eda-worker",
        "eda-cli",
        "import",
        "eda-import",
        "sim-import",
        "nginx",
    }
    assert "timescale/timescaledb:2.28.3-pg17" in compose
    assert "    volumes:\n      - db_data:/var/lib/postgresql/data" in services["db"]
    assert "    ports:" not in services["db"]
    assert all(
        "    ports:" not in services[name]
        for name in (
            "migrate",
            "seed",
            "api",
            "worker",
            "eda-worker",
            "eda-cli",
            "eda-import",
            "sim-import",
        )
    )
    assert services["nginx"].count("    ports:") == 1
    assert '      - "${NGINX_PORT}:80"' in services["nginx"]
    assert '    profiles: ["ops"]' in services["eda-cli"]
    assert '    profiles: ["eda-import"]' in services["eda-import"]
    assert "    profiles:" not in services["eda-worker"]


def test_compose_enforces_the_database_seed_api_nginx_dependency_chain() -> None:
    project_root = Path(os.environ["PROJECT_ROOT"])
    compose = (project_root / "compose.yaml").read_text(encoding="utf-8")
    services = _compose_services(compose)

    assert (
        'pg_isready -h 127.0.0.1 -U "$${POSTGRES_USER}" -d "$${POSTGRES_DB}"'
        in services["db"]
    )
    assert "      db:\n        condition: service_healthy" in services["migrate"]
    assert "      migrate:\n        condition: service_completed_successfully" in services["seed"]
    assert "      seed:\n        condition: service_completed_successfully" in services["api"]
    for name in ("worker", "eda-worker", "eda-cli", "eda-import", "sim-import"):
        assert (
            "      seed:\n        condition: service_completed_successfully"
            in services[name]
        )
    assert "urllib.request" in services["api"]
    assert "http://127.0.0.1:8000/health" in services["api"]
    assert "      api:\n        condition: service_healthy" in services["nginx"]
    for name in ("migrate", "seed", "api", "worker", "eda-cli"):
        assert _environment_keys(services[name]) == set(DATABASE_ENV)
    assert _environment_keys(services["eda-worker"]) == set(DATABASE_ENV) | {
        "EDA_WORKER_LEASE_SECONDS",
        "EDA_WORKER_HEARTBEAT_SECONDS",
        "EDA_WORKER_MAX_ATTEMPTS",
        "EDA_WORKER_COMPUTE_TIMEOUT_SECONDS",
    }
    assert _environment_keys(services["eda-import"]) == set(DATABASE_ENV) | {
        "EDA_RAW_SOURCE_PATH",
        "EDA_SOURCE_MANIFEST_PATH",
        "EDA_SOURCE_MANIFEST_SHA256",
    }
    assert _environment_keys(services["sim-import"]) == set(DATABASE_ENV) | {
        "SIM_INJECTED_NPZ_PATH",
        "SIM_INJECTED_EVENTS_PATH",
    }


def test_compose_uses_only_checked_in_build_contexts_and_private_backend_network() -> None:
    project_root = Path(os.environ["PROJECT_ROOT"])
    compose = (project_root / "compose.yaml").read_text(encoding="utf-8")
    services = _compose_services(compose)

    for name in ("migrate", "seed", "api", "eda-cli"):
        assert "    build:\n      context: ./backend\n      target: runtime" in services[name]
        assert "    volumes:" not in services[name]
        assert "      - backend" in services[name]
        assert "      - public" not in services[name]
    assert "    build:\n      context: ./backend\n      target: worker" in services["worker"]
    assert (
        "    build:\n      context: ./backend\n      target: eda-worker"
        in services["eda-worker"]
    )
    assert "    volumes:" not in services["eda-worker"]
    assert "      - backend" in services["eda-worker"]
    assert "      - public" not in services["eda-worker"]
    assert '    command: ["python", "-m", "anomaly_worker.eda_service"]' in services[
        "eda-worker"
    ]
    assert '          memory: "2147483648"' in services["eda-worker"]
    assert (
        '    entrypoint: ["python", "-m", "anomaly_backend.eda_cli"]'
        in services["eda-cli"]
    )
    assert '    command: ["--help"]' in services["eda-cli"]
    assert "    build:\n      context: ./backend\n      target: eda-worker" in services[
        "eda-import"
    ]
    assert (
        '    command: ["python", "-m", "anomaly_backend.eda_importer"]'
        in services["eda-import"]
    )
    assert services["eda-import"].count(":ro\"") == 2
    assert "      - backend" in services["eda-import"]
    assert "      - public" not in services["eda-import"]
    assert "    build:\n      context: ./backend\n      target: eda-worker" in services[
        "sim-import"
    ]
    assert (
        '    command: ["python", "-m", "anomaly_backend.sim_importer"]'
        in services["sim-import"]
    )
    assert services["sim-import"].count(":ro\"") == 1
    assert "      - backend" in services["sim-import"]
    assert "      - public" not in services["sim-import"]
    assert '    command: ["python", "-m", "anomaly_backend.seed"]' in services["seed"]
    assert "    build:\n      context: ./frontend" in services["nginx"]
    assert "      - backend" in services["nginx"]
    assert "      - public" in services["nginx"]
    assert "networks:\n  backend:\n    internal: true\n  public:" in compose
    for forbidden in ("../", "data/processed", "runs/", "test.npz"):
        assert forbidden not in compose


def test_environment_example_adds_only_nginx_port_to_database_settings() -> None:
    project_root = Path(os.environ["PROJECT_ROOT"])
    environment_example = (project_root / ".env.example").read_text(encoding="utf-8")
    keys = {
        line.partition("=")[0]
        for line in environment_example.splitlines()
        if line and not line.startswith("#")
    }

    assert keys == set(DATABASE_ENV) | {
        "NGINX_PORT",
        "B02_RAW_ARCHIVE_PATH",
        "EDA_WORKER_LEASE_SECONDS",
        "EDA_WORKER_HEARTBEAT_SECONDS",
        "EDA_WORKER_MAX_ATTEMPTS",
        "EDA_WORKER_COMPUTE_TIMEOUT_SECONDS",
        "EDA_RAW_SOURCE_PATH",
        "EDA_SOURCE_MANIFEST_PATH",
        "EDA_SOURCE_MANIFEST_SHA256",
    }
    assert "./REPLACE_WITH_B02_V3_SOURCE/sensor_data_long.csv" in environment_example
    assert "<verify-from-eda-worker>" in environment_example


def test_direct_dependencies_are_exactly_pinned() -> None:
    project_root = Path(os.environ["PROJECT_ROOT"])
    with (project_root / "backend" / "pyproject.toml").open("rb") as pyproject_file:
        pyproject = tomllib.load(pyproject_file)

    assert pyproject["project"]["dependencies"] == [
        "fastapi==0.139.2",
        "pydantic==2.13.4",
        "uvicorn==0.51.0",
        "sqlalchemy[asyncio]==2.0.51",
        "psycopg[binary]==3.3.2",
        "alembic==1.18.5",
    ]
    assert pyproject["project"]["optional-dependencies"]["test"] == [
        "pytest==9.1.0",
        "httpx==0.28.1",
        "anyio==4.14.2",
    ]
    assert pyproject["project"]["optional-dependencies"]["eda"] == [
        "numpy==2.4.6",
        "pandas==2.3.3",
        "matplotlib==3.11.0",
        "scipy==1.17.1",
        "statsmodels==0.14.6",
        "ruptures==1.1.10",
        "scikit-learn==1.9.0",
        "seaborn==0.13.2",
    ]


def test_built_wheel_contains_route_and_sql_marker_packages() -> None:
    package = resources.files("anomaly_backend")

    assert package.joinpath("routes/__init__.py").is_file()
    assert package.joinpath("sql/__init__.py").is_file()
    assert package.joinpath(
        "fixtures/dandy_pilot/normalized_pilot_snapshot.json"
    ).is_file()

from importlib.metadata import version
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


EXPECTED_EDA_VERSIONS = {
    "numpy": "2.4.6",
    "pandas": "2.3.3",
    "matplotlib": "3.11.0",
    "scipy": "1.17.1",
    "statsmodels": "0.14.6",
    "ruptures": "1.1.10",
    "scikit-learn": "1.9.0",
    "seaborn": "0.13.2",
}
HEAVY_MODULES = {"numpy", "scipy", "statsmodels", "ruptures"}
SOURCE_REPOSITORY = Path("/home/reky/college/skripsih/anomaly-detection")
TOOLCHAIN_ROLE = os.environ.get("EDA_TOOLCHAIN_ROLE")


def test_toolchain_role_is_explicit() -> None:
    assert TOOLCHAIN_ROLE in {"api", "eda-worker"}


@pytest.mark.skipif(TOOLCHAIN_ROLE != "eda-worker", reason="EDA worker image only")
def test_eda_worker_runtime_and_dependencies() -> None:
    assert sys.version_info[:2] == (3, 12)
    assert {
        distribution: version(distribution)
        for distribution in EXPECTED_EDA_VERSIONS
    } == EXPECTED_EDA_VERSIONS
    output = subprocess.check_output(
        [sys.executable, "-m", "anomaly_eda"],
        text=True,
    )
    assert json.loads(output) == {
        "algorithm": (
            "bivariate_b02f3872_eda_v3+vendor."
            "37565a5341be56e9a0a88d55ce1dbfe6ae25b0fe"
        ),
        **EXPECTED_EDA_VERSIONS,
    }


@pytest.mark.skipif(TOOLCHAIN_ROLE != "eda-worker", reason="EDA worker image only")
def test_eda_import_entrypoint_has_authoritative_config_package() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from anomaly_backend.eda_importer import CONFIG_HASH as imported; "
                "from anomaly_eda.config import CONFIG_HASH as authoritative; "
                "assert imported == authoritative; print(imported)"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == (
        "1081a79b8452075df4baf2f88f6ed3094f90286c0e17ee7d666e0b8072ba8452"
    )


@pytest.mark.skipif(TOOLCHAIN_ROLE != "api", reason="API image only")
def test_api_runtime_and_dependency_isolation() -> None:
    assert sys.version_info[:2] == (3, 13)
    import_check = "; ".join(
        (
            "import anomaly_backend, importlib.util, sys",
            f"names = {tuple(HEAVY_MODULES)!r}",
            "assert all(importlib.util.find_spec(name) is None for name in names)",
            f"assert not {HEAVY_MODULES!r} & sys.modules.keys()",
        )
    )
    result = subprocess.run(
        [sys.executable, "-c", import_check],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(TOOLCHAIN_ROLE != "api", reason="API/runtime image only")
def test_eda_cli_help_does_not_require_eda_compute_dependencies() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "anomaly_backend.eda_cli", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "Exact full backfill command" in result.stdout


def test_source_repository_is_not_injected_into_python_paths() -> None:
    configured_paths = [*sys.path, os.environ.get("PYTHONPATH", "")]
    for configured_path in configured_paths:
        for path_entry in configured_path.split(os.pathsep):
            if not path_entry:
                continue
            resolved = Path(path_entry).resolve()
            assert resolved != SOURCE_REPOSITORY
            assert SOURCE_REPOSITORY not in resolved.parents

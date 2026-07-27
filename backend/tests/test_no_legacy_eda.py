from __future__ import annotations

import ast
import gzip
import os
import re
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
EDA_TEXT_FILES = (
    "anomaly_backend/eda_cli.py",
    "anomaly_backend/eda_contracts.py",
    "anomaly_backend/eda_importer.py",
    "anomaly_backend/routes/eda.py",
    "anomaly_backend/sql/eda_runs.py",
    "anomaly_worker/eda_service.py",
    "anomaly_eda/__init__.py",
    "anomaly_eda/__main__.py",
    "anomaly_eda/change_points.py",
    "anomaly_eda/config.py",
    "anomaly_eda/input_adapter.py",
    "anomaly_eda/pair_product.py",
    "anomaly_eda/quality.py",
    "anomaly_eda/relationships.py",
    "anomaly_eda/stationarity.py",
    "anomaly_eda/temporal.py",
    "anomaly_eda/uncertainty.py",
    "tests/fixtures/eda_authority/extract_goldens.py",
    "tests/fixtures/eda_authority/goldens.json",
)
EDA_GZIP_FILES = ("tests/fixtures/eda_authority/golden_arrays.json.gz",)
FORBIDDEN_TOKENS = (
    "TALPHA",
    "talphaValidationRange",
    "candidate_outlier",
    "candidateOutlier",
    "score_provenance",
    "model_version",
    "simulated_preview",
    "artifact_backed",
    "86,104",
    "86104",
)


def _forbidden_matches(relative_path: str, source: str) -> list[str]:
    def contains(token: str) -> bool:
        if token == "86104":
            return re.search(r"(?<![\d.])86104(?!\d)", source) is not None
        if token == "86,104":
            return re.search(r"(?<!\d)86,104(?!\d)", source) is not None
        return token in source

    return [
        f"{relative_path}: {token}"
        for token in FORBIDDEN_TOKENS
        if contains(token)
    ]


def test_backend_eda_scope_has_no_legacy_tokens() -> None:
    matches: list[str] = []
    for relative_path in EDA_TEXT_FILES:
        path = BACKEND_ROOT / relative_path
        if (
            not path.is_file()
            and os.environ.get("EDA_TOOLCHAIN_ROLE") == "api"
            and relative_path.startswith("anomaly_eda/")
        ):
            continue
        assert path.is_file(), f"EDA guard allowlist path is missing: {relative_path}"
        matches.extend(_forbidden_matches(relative_path, path.read_text(encoding="utf-8")))
    for relative_path in EDA_GZIP_FILES:
        path = BACKEND_ROOT / relative_path
        assert path.is_file(), f"EDA guard allowlist path is missing: {relative_path}"
        with gzip.open(path, "rt", encoding="utf-8") as fixture:
            matches.extend(_forbidden_matches(relative_path, fixture.read()))
    assert matches == []


def test_legacy_common_contract_eda_models_stay_removed() -> None:
    source = (BACKEND_ROOT / "anomaly_backend/contracts.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = [
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name.startswith("Eda")
    ]
    assert names == []
    assert "EdaField =" not in source


def test_retired_eda_sql_and_bytecode_stay_removed() -> None:
    assert not (BACKEND_ROOT / "anomaly_backend/sql/eda.py").exists()
    assert list(
        (BACKEND_ROOT / "anomaly_backend/sql/__pycache__").glob(
            "eda.cpython-*.pyc"
        )
    ) == []

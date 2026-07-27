from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType
from typing import Any


SOURCE_RELEASE_ID = "bivariate_b02f3872_eda_v3"
PLATFORM_VENDOR_COMMIT_SHA = "37565a5341be56e9a0a88d55ce1dbfe6ae25b0fe"
ALGORITHM_VERSION = f"{SOURCE_RELEASE_ID}+vendor.{PLATFORM_VENDOR_COMMIT_SHA}"

DEVICE_ID = "b02f3872-39a2-4b6f-a4ec-045a287fde4b"
DATASET_ID = "bivariate_b02f3872_v1"
TIME_ZONE = "Asia/Jakarta"
SEED = 20260724
BUFFER_BYTES = 1_048_576
MAXIMUM_CHUNK_PAIRS = 250_000
MAXIMUM_PEAK_RSS_BYTES = 2_147_483_648


@dataclass(frozen=True, slots=True)
class QualityParameters:
    suhu_lower_exclusive: float = 0.0
    suhu_upper_inclusive: float = 60.0
    rh_lower_exclusive: float = 0.0
    rh_upper_inclusive: float = 100.0
    near_zero_absolute: float = 0.000001
    stale_duration_seconds: int = 600


@dataclass(frozen=True, slots=True)
class CadenceParameters:
    expected_seconds: int = 6
    acceptance_min_seconds: int = 5
    acceptance_max_seconds: int = 7
    positive_delta_ceiling_seconds: int = 30
    primary_gap_seconds: int = 30
    gap_sensitivity_seconds: tuple[int, int] = (15, 60)


@dataclass(frozen=True, slots=True)
class CoverageParameters:
    sensitivity_thresholds: tuple[float, float, float] = (0.50, 0.80, 0.95)
    primary_threshold: float = 0.80
    partial_exposure_fraction: float = 0.75
    minimum_eligible_nonpartial_days: int = 15
    dense_consecutive_months: int = 3


@dataclass(frozen=True, slots=True)
class RollingParameters:
    primary_window_minutes: int = 30
    sensitivity_window_minutes: tuple[int, int, int] = (15, 60, 180)
    minimum_coverage: float = 0.80
    minimum_pairs: int = 30
    maximum_reported_points: int = 2_000


@dataclass(frozen=True, slots=True)
class StationarityParameters:
    primary_minimum_days: int = 30
    sensitivity_minimum_days: int = 14
    maximum_sensitivity_segments: int = 3
    stl_period: int = 24
    stl_seasonal: int = 25
    stl_trend: int = 169
    stl_low_pass: int = 25
    stl_robust: bool = True
    adf_level_regression: str = "ct"
    adf_derived_regression: str = "c"
    adf_autolag: str = "AIC"
    maximum_lag: int = 72
    kpss_level_regression: str = "ct"
    kpss_derived_regression: str = "c"
    kpss_nlags: str = "auto"
    pacf_method: str = "ywm"


@dataclass(frozen=True, slots=True)
class ChangePointParameters:
    minimum_block_days: int = 90
    kernel: str = "linear"
    kernel_minimum_segment_days: int = 14
    kernel_jump: int = 1
    penalty_factors: tuple[int, int, int, int] = (1, 2, 4, 8)
    stability_radius_days: int = 3
    stability_minimum_penalties: int = 3
    binseg_model: str = "l1"
    binseg_minimum_segment_days: tuple[int, int, int] = (7, 14, 28)


@dataclass(frozen=True, slots=True)
class BootstrapParameters:
    replicates: int = 2_000
    seed: int = SEED
    primary_block_days: int = 14
    sensitivity_block_days: tuple[int, int] = (7, 28)
    confidence_level: float = 0.95
    minimum_paired_days: int = 30


@dataclass(frozen=True, slots=True)
class BinningParameters:
    suhu_lower: float = 0.0
    suhu_upper: float = 60.0
    rh_lower: float = 0.0
    rh_upper: float = 100.0
    joint_suhu_bins: int = 120
    joint_rh_bins: int = 200
    univariate_suhu_bins: int = 600
    univariate_rh_bins: int = 400


@dataclass(frozen=True, slots=True)
class ExcerptParameters:
    context_seconds: int = 1_800
    maximum_points: int = 2_000


@dataclass(frozen=True, slots=True)
class StreamingParameters:
    buffer_bytes: int = BUFFER_BYTES
    maximum_chunk_pairs: int = MAXIMUM_CHUNK_PAIRS


@dataclass(frozen=True, slots=True)
class EdaComputeConfig:
    quality: QualityParameters = QualityParameters()
    cadence: CadenceParameters = CadenceParameters()
    coverage: CoverageParameters = CoverageParameters()
    rolling: RollingParameters = RollingParameters()
    stationarity: StationarityParameters = StationarityParameters()
    change_point: ChangePointParameters = ChangePointParameters()
    bootstrap: BootstrapParameters = BootstrapParameters()
    binning: BinningParameters = BinningParameters()
    excerpt: ExcerptParameters = ExcerptParameters()
    streaming: StreamingParameters = StreamingParameters()


DEFAULT_CONFIG = EdaComputeConfig()


_V2_PARAMETERS: dict[str, Any] = {
    "identity": {
        "schema_version": "bivariate_b02f3872_eda_config_v2",
        "dataset_id": DATASET_ID,
        "release_id": "bivariate_b02f3872_eda_v2",
        "timezone": TIME_ZONE,
        "seed": SEED,
    },
    "input": {
        "raw_csv": "data/raw/bivariate_b02f3872_v1/sensor_data_long.csv",
        "source_manifest": "docs/artifacts/manifests/bivariate_b02f3872_source_v1.json",
        "expected_source_sha256": "b8ae739a427681735792f02eea14dd8b7fc53f5265630a7e9a62b846f7b8040f",
        "expected_source_manifest_sha256": "196178e7424bd2e92268606f0ef33237d2329bdfefd9dce592283c07a697d486",
        "device_id": DEVICE_ID,
        "data_indices": [0, 1],
    },
    "views": {
        "pair_key": "exact_timestamp",
        "resolvers": ["median", "min", "max", "drop_conflicting"],
        "primary_resolver": "median",
        "identical_duplicate_sensitivity": True,
    },
    "quality": {
        "suhu_lower_exclusive": 0.0,
        "suhu_upper_inclusive": 60.0,
        "rh_lower_exclusive": 0.0,
        "rh_upper_inclusive": 100.0,
        "near_zero_absolute": 0.000001,
        "zero_gap_proximity_seconds": [60, 600],
        "zero_episode_gap_seconds": 30,
        "stale_duration_seconds": [30, 120, 600],
        "duplicate_example_limit": 20,
        "event_example_limit": 20,
    },
    "cadence": {
        "expected_seconds": 6,
        "acceptance_min_seconds": 5,
        "acceptance_max_seconds": 7,
        "positive_delta_ceiling_seconds": 30,
        "primary_gap_seconds": 30,
        "gap_sensitivity_seconds": [15, 60],
    },
    "coverage": {
        "sensitivity_thresholds": [0.50, 0.80, 0.95],
        "primary_threshold": 0.80,
        "partial_exposure_fraction": 0.75,
        "minimum_eligible_nonpartial_days": 15,
        "dense_consecutive_months": 3,
    },
    "rolling": {
        "primary_window_minutes": 30,
        "sensitivity_window_minutes": [15, 60, 180],
        "minimum_coverage": 0.80,
        "minimum_pairs": 30,
        "maximum_reported_points": 2_000,
    },
    "lags": {
        "exact_seconds": [0, -5, 5, -6, 6, -7, 7, -12, 12, -30, 30, -60, 60, -120, 120, -180, 180, -300, 300, -600, 600],
        "slow_hours": [0, -1, 1, -2, 2, -3, 3, -6, 6, -12, 12, -24, 24],
    },
    "bootstrap": {
        "replicates": 2_000,
        "seed": SEED,
        "primary_block_days": 14,
        "sensitivity_block_days": [7, 28],
        "confidence_level": 0.95,
        "minimum_paired_days": 30,
    },
    "stationarity": {
        "primary_minimum_days": 30,
        "sensitivity_minimum_days": 14,
        "maximum_sensitivity_segments": 3,
        "stl_period": 24,
        "stl_seasonal": 25,
        "stl_trend": 169,
        "stl_low_pass": 25,
        "stl_robust": True,
        "adf_level_regression": "ct",
        "adf_derived_regression": "c",
        "adf_autolag": "AIC",
        "maximum_lag": 72,
        "kpss_level_regression": "ct",
        "kpss_derived_regression": "c",
        "kpss_nlags": "auto",
        "pacf_method": "ywm",
    },
    "change_point": {
        "minimum_block_days": 90,
        "kernel": "linear",
        "kernel_minimum_segment_days": 14,
        "kernel_jump": 1,
        "penalty_factors": [1, 2, 4, 8],
        "stability_radius_days": 3,
        "stability_minimum_penalties": 3,
        "binseg_model": "l1",
        "binseg_minimum_segment_days": [7, 14, 28],
    },
}

_V3_PARAMETERS: dict[str, Any] = {
    "identity": {
        "schema_version": "bivariate_b02f3872_eda_config_v3",
        "dataset_id": DATASET_ID,
        "release_id": SOURCE_RELEASE_ID,
        "timezone": TIME_ZONE,
        "seed": SEED,
    },
    "input": {
        "raw_csv": "data/raw/bivariate_b02f3872_v1/sensor_data_long.csv",
        "source_manifest": "docs/artifacts/manifests/bivariate_b02f3872_source_v1.json",
        "expected_source_sha256": "b8ae739a427681735792f02eea14dd8b7fc53f5265630a7e9a62b846f7b8040f",
        "expected_source_manifest_sha256": "196178e7424bd2e92268606f0ef33237d2329bdfefd9dce592283c07a697d486",
        "device_id": DEVICE_ID,
        "data_indices": [0, 1],
    },
    "quality": {
        "suhu_lower_exclusive": 0.0,
        "suhu_upper_inclusive": 60.0,
        "rh_lower_exclusive": 0.0,
        "rh_upper_inclusive": 100.0,
        "near_zero_absolute": 0.000001,
        "stale_duration_seconds": 600,
    },
    "cadence": {
        "expected_seconds": 6,
        "acceptance_min_seconds": 5,
        "acceptance_max_seconds": 7,
        "primary_gap_seconds": 30,
    },
    "binning": {
        "suhu_lower": 0.0,
        "suhu_upper": 60.0,
        "rh_lower": 0.0,
        "rh_upper": 100.0,
        "joint_suhu_bins": 120,
        "joint_rh_bins": 200,
        "univariate_suhu_bins": 600,
        "univariate_rh_bins": 400,
    },
    "excerpt": {"context_seconds": 1_800, "maximum_points": 2_000},
    "streaming": {
        "buffer_bytes": BUFFER_BYTES,
        "maximum_chunk_pairs": MAXIMUM_CHUNK_PAIRS,
    },
}

def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(child) for key, child in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(child) for child in value)
    return value


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _json_value(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_json_value(child) for child in value]
    return value


CANONICAL_CONFIG_PARAMETERS: Mapping[str, Any] = _freeze(
    {"v2": _V2_PARAMETERS, "v3": _V3_PARAMETERS}
)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        _json_value(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


CONFIG_HASH = hashlib.sha256(
    canonical_json_bytes(CANONICAL_CONFIG_PARAMETERS)
).hexdigest()


__all__ = [
    "ALGORITHM_VERSION",
    "BinningParameters",
    "BootstrapParameters",
    "BUFFER_BYTES",
    "CANONICAL_CONFIG_PARAMETERS",
    "CONFIG_HASH",
    "CadenceParameters",
    "ChangePointParameters",
    "CoverageParameters",
    "DATASET_ID",
    "DEFAULT_CONFIG",
    "DEVICE_ID",
    "EdaComputeConfig",
    "ExcerptParameters",
    "MAXIMUM_CHUNK_PAIRS",
    "MAXIMUM_PEAK_RSS_BYTES",
    "PLATFORM_VENDOR_COMMIT_SHA",
    "QualityParameters",
    "RollingParameters",
    "SEED",
    "SOURCE_RELEASE_ID",
    "StationarityParameters",
    "StreamingParameters",
    "TIME_ZONE",
    "canonical_json_bytes",
]

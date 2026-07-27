from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from typing import Literal, cast
import warnings

import numpy as np  # pyright: ignore[reportMissingImports]
from scipy.signal import periodogram  # pyright: ignore[reportMissingImports]
from statsmodels.tsa.seasonal import STL  # pyright: ignore[reportMissingImports]
from statsmodels.tsa.stattools import (  # pyright: ignore[reportMissingImports]
    acf,
    adfuller,
    kpss,
    pacf,
)

from .config import DEFAULT_CONFIG, EdaComputeConfig, StationarityParameters
from .pair_product import VIEW_SCREENED
from .temporal import TemporalComputeResult, hourly_median_aggregates


DiagnosticStatus = Literal["ok", "short", "constant", "nonfinite", "error"]
StationarityReason = Literal[
    "insufficient_stationarity_sensitivity_tier",
    "insufficient_stationarity_primary_tier",
]


@dataclass(frozen=True, slots=True)
class HypothesisTestResult:
    status: DiagnosticStatus
    null_hypothesis: str
    statistic: float | None
    p_value: float | None
    lags: int | None
    observations: int
    error: str | None = None


@dataclass(frozen=True, slots=True)
class CorrelationSequenceResult:
    status: DiagnosticStatus
    method: str
    values: np.ndarray
    maximum_lag: int
    error: str | None = None


@dataclass(frozen=True, slots=True)
class PeriodogramResult:
    status: DiagnosticStatus
    frequencies: np.ndarray
    power: np.ndarray
    error: str | None = None


@dataclass(frozen=True, slots=True)
class STLResult:
    status: DiagnosticStatus
    seasonal: np.ndarray
    trend: np.ndarray
    residual: np.ndarray
    error: str | None = None


@dataclass(frozen=True, slots=True)
class StationarityBundle:
    level_adf: HypothesisTestResult
    difference_adf: HypothesisTestResult
    residual_adf: HypothesisTestResult
    level_kpss: HypothesisTestResult
    difference_kpss: HypothesisTestResult
    residual_kpss: HypothesisTestResult
    autocorrelation: CorrelationSequenceResult
    partial_autocorrelation: CorrelationSequenceResult
    spectrum: PeriodogramResult
    stl: STLResult


@dataclass(frozen=True, slots=True)
class StationarityComputeResult:
    status: Literal["complete", "not_eligible"]
    reason_code: StationarityReason | None
    payload: dict[str, object] | None
    audit_metadata: dict[str, object]


def _series(values: np.ndarray) -> np.ndarray:
    result = np.asarray(values, dtype=np.float64)
    if result.ndim != 1:
        raise ValueError("series must be one-dimensional")
    return result


def _preflight(values: np.ndarray, minimum: int) -> DiagnosticStatus:
    if not np.all(np.isfinite(values)):
        return "nonfinite"
    if values.size < minimum:
        return "short"
    if np.ptp(values) == 0.0:
        return "constant"
    return "ok"


def _adf(
    values: np.ndarray,
    *,
    regression: Literal["c", "ct"],
    autolag: Literal["AIC", "BIC", "t-stat"],
    maximum_lag: int,
) -> HypothesisTestResult:
    series = _series(values)
    status = _preflight(series, 8)
    if status != "ok":
        return HypothesisTestResult(
            status, "unit root is present", None, None, None, int(series.size)
        )
    deterministic_terms = 1 if regression == "c" else 2
    maxlag = max(0, min(maximum_lag, series.size // 2 - deterministic_terms - 1))
    try:
        statistic, p_value, used_lag, observations, *_ = adfuller(
            series,
            maxlag=maxlag,
            regression=regression,
            autolag=autolag,
        )
    except (ValueError, np.linalg.LinAlgError) as error:
        return HypothesisTestResult(
            "error",
            "unit root is present",
            None,
            None,
            None,
            int(series.size),
            str(error),
        )
    return HypothesisTestResult(
        "ok",
        "unit root is present",
        float(statistic),
        float(p_value),
        int(used_lag),
        int(observations),
    )


def _kpss(
    values: np.ndarray,
    *,
    regression: Literal["c", "ct"],
    nlags: Literal["auto"],
) -> HypothesisTestResult:
    series = _series(values)
    status = _preflight(series, 8)
    null = "trend-stationary" if regression == "ct" else "level-stationary"
    if status != "ok":
        return HypothesisTestResult(status, null, None, None, None, int(series.size))
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            statistic, p_value, lags, _ = kpss(
                series, regression=regression, nlags=nlags
            )
    except (ValueError, np.linalg.LinAlgError, OverflowError) as error:
        return HypothesisTestResult(
            "error", null, None, None, None, int(series.size), str(error)
        )
    return HypothesisTestResult(
        "ok", null, float(statistic), float(p_value), int(lags), int(series.size)
    )


def _stl(values: np.ndarray, config: StationarityParameters) -> STLResult:
    series = _series(values)
    status = _preflight(series, config.stl_period * config.sensitivity_minimum_days)
    if status != "ok":
        empty = np.empty(0, dtype=np.float64)
        return STLResult(status, empty, empty, empty)
    try:
        fit = STL(
            series,
            period=config.stl_period,
            seasonal=config.stl_seasonal,
            trend=config.stl_trend,
            low_pass=config.stl_low_pass,
            robust=config.stl_robust,
        ).fit()
    except (ValueError, np.linalg.LinAlgError) as error:
        empty = np.empty(0, dtype=np.float64)
        return STLResult("error", empty, empty, empty, str(error))
    return STLResult(
        "ok",
        np.asarray(fit.seasonal, dtype=np.float64),
        np.asarray(fit.trend, dtype=np.float64),
        np.asarray(fit.resid, dtype=np.float64),
    )


def _acf(values: np.ndarray, maximum_lag: int) -> CorrelationSequenceResult:
    series = _series(values)
    maximum_lag = min(maximum_lag, series.size // 2 - 1)
    status = _preflight(series, 4)
    if status != "ok" or maximum_lag < 1:
        return CorrelationSequenceResult(
            "short" if maximum_lag < 1 and status == "ok" else status,
            "acf_fft",
            np.empty(0, dtype=np.float64),
            max(0, maximum_lag),
        )
    try:
        result = acf(series, nlags=maximum_lag, fft=True)
    except (ValueError, np.linalg.LinAlgError) as error:
        return CorrelationSequenceResult(
            "error",
            "acf_fft",
            np.empty(0, dtype=np.float64),
            maximum_lag,
            str(error),
        )
    return CorrelationSequenceResult(
        "ok", "acf_fft", np.asarray(result, dtype=np.float64), maximum_lag
    )


def _pacf(
    values: np.ndarray, maximum_lag: int, method: Literal["ywm", "yw", "ols"]
) -> CorrelationSequenceResult:
    series = _series(values)
    maximum_lag = min(maximum_lag, series.size // 2 - 1)
    status = _preflight(series, 4)
    if status != "ok" or maximum_lag < 1:
        return CorrelationSequenceResult(
            "short" if maximum_lag < 1 and status == "ok" else status,
            f"pacf_{method}",
            np.empty(0, dtype=np.float64),
            max(0, maximum_lag),
        )
    try:
        result = pacf(series, nlags=maximum_lag, method=method)
    except (ValueError, np.linalg.LinAlgError) as error:
        return CorrelationSequenceResult(
            "error",
            f"pacf_{method}",
            np.empty(0, dtype=np.float64),
            maximum_lag,
            str(error),
        )
    return CorrelationSequenceResult(
        "ok", f"pacf_{method}", np.asarray(result, dtype=np.float64), maximum_lag
    )


def _spectrum(values: np.ndarray) -> PeriodogramResult:
    series = _series(values)
    status = _preflight(series, 4)
    if status != "ok":
        empty = np.empty(0, dtype=np.float64)
        return PeriodogramResult(status, empty, empty)
    try:
        frequencies, power = periodogram(series)
    except (ValueError, np.linalg.LinAlgError) as error:
        empty = np.empty(0, dtype=np.float64)
        return PeriodogramResult("error", empty, empty, str(error))
    return PeriodogramResult(
        "ok",
        np.asarray(frequencies, dtype=np.float64),
        np.asarray(power, dtype=np.float64),
    )


def stationarity_bundle(
    values: np.ndarray, config: StationarityParameters
) -> StationarityBundle:
    series = _series(values)
    stl = _stl(series, config)
    difference = np.diff(series) if np.all(np.isfinite(series)) else series
    residual = stl.residual if stl.status == "ok" else np.empty(0, dtype=np.float64)
    return StationarityBundle(
        level_adf=_adf(
            series,
            regression=cast(Literal["c", "ct"], config.adf_level_regression),
            autolag=cast(Literal["AIC", "BIC", "t-stat"], config.adf_autolag),
            maximum_lag=config.maximum_lag,
        ),
        difference_adf=_adf(
            difference,
            regression=cast(Literal["c", "ct"], config.adf_derived_regression),
            autolag=cast(Literal["AIC", "BIC", "t-stat"], config.adf_autolag),
            maximum_lag=config.maximum_lag,
        ),
        residual_adf=_adf(
            residual,
            regression=cast(Literal["c", "ct"], config.adf_derived_regression),
            autolag=cast(Literal["AIC", "BIC", "t-stat"], config.adf_autolag),
            maximum_lag=config.maximum_lag,
        ),
        level_kpss=_kpss(
            series,
            regression=cast(Literal["c", "ct"], config.kpss_level_regression),
            nlags=cast(Literal["auto"], config.kpss_nlags),
        ),
        difference_kpss=_kpss(
            difference,
            regression=cast(Literal["c", "ct"], config.kpss_derived_regression),
            nlags=cast(Literal["auto"], config.kpss_nlags),
        ),
        residual_kpss=_kpss(
            residual,
            regression=cast(Literal["c", "ct"], config.kpss_derived_regression),
            nlags=cast(Literal["auto"], config.kpss_nlags),
        ),
        autocorrelation=_acf(series, config.maximum_lag),
        partial_autocorrelation=_pacf(
            series,
            config.maximum_lag,
            cast(Literal["ywm", "yw", "ols"], config.pacf_method),
        ),
        spectrum=_spectrum(series),
        stl=stl,
    )


def _json_ready(value: object) -> object:
    if isinstance(value, np.ndarray):
        return cast(np.ndarray, value).tolist()
    if is_dataclass(value) and not isinstance(value, type):
        return _json_ready(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.generic):
        return cast(np.generic, value).item()
    return value


def _run_segment(
    description: dict[str, object],
    hourly: list[dict[str, object]],
    config: StationarityParameters,
) -> dict[str, object]:
    if description["status"] != "ok":
        return {"status": description["status"]}
    start, stop = cast(list[int], description["positions"])
    records = hourly[start : stop + 1]
    medians = np.asarray(
        [
            (
                cast(
                    dict[str, object],
                    cast(dict[str, object], record["statistics"])["suhu"],
                )["median"],
                cast(
                    dict[str, object],
                    cast(dict[str, object], record["statistics"])["rh"],
                )["median"],
            )
            for record in records
        ],
        dtype=np.float64,
    )
    return {
        "status": "ok",
        "start": description["start"],
        "end": description["end"],
        "hours": description["hours"],
        "suhu": _json_ready(stationarity_bundle(medians[:, 0], config)),
        "rh": _json_ready(stationarity_bundle(medians[:, 1], config)),
    }


def _published_channel(channel: dict[str, object]) -> dict[str, object]:
    return {
        "autocorrelation": channel["autocorrelation"],
        "partial_autocorrelation": channel["partial_autocorrelation"],
        "spectrum": channel["spectrum"],
        "stl": channel["stl"],
    }


def _published_segment(segment: dict[str, object]) -> dict[str, object]:
    return {
        "status": segment["status"],
        "start": segment["start"],
        "end": segment["end"],
        "hours": segment["hours"],
        "channels": {
            channel: _published_channel(cast(dict[str, object], segment[channel]))
            for channel in ("suhu", "rh")
        },
    }


def compute_stationarity(
    result: TemporalComputeResult,
    config: EdaComputeConfig = DEFAULT_CONFIG,
) -> StationarityComputeResult:
    hourly = hourly_median_aggregates(result, VIEW_SCREENED)
    selection = cast(
        dict[str, object],
        cast(dict[str, object], result.temporal_coverage["views"])[VIEW_SCREENED],
    )["eligible_hour_segments"]
    selection = cast(dict[str, object], selection)
    primary = _run_segment(
        cast(dict[str, object], selection["primary"]), hourly, config.stationarity
    )
    sensitivity = [
        _run_segment(item, hourly, config.stationarity)
        for item in cast(list[dict[str, object]], selection["sensitivity"])
    ]
    audit: dict[str, object] = {
        "method_notice": (
            "ADF and KPSS retain distinct null hypotheses and are diagnostics, "
            "not cleaning or modeling gates."
        ),
        "primary": primary,
        "sensitivity": sensitivity,
    }
    diagnostics = [primary, *sensitivity]
    leaf_statuses = {
        cast(dict[str, object], result)["status"]
        for diagnostic in diagnostics
        for channel in ("suhu", "rh")
        for result in (
            cast(dict[str, object], diagnostic.get(channel, {})).values()
            if isinstance(diagnostic.get(channel), dict)
            else ()
        )
        if isinstance(result, dict)
    }
    audit["status"] = (
        "failed"
        if leaf_statuses & {"error", "nonfinite", "short"}
        else "complete"
        if any(item.get("status") == "ok" for item in diagnostics)
        else "not_applicable"
    )
    if not sensitivity:
        return StationarityComputeResult(
            "not_eligible",
            "insufficient_stationarity_sensitivity_tier",
            None,
            audit,
        )
    primary_payload = _published_segment(primary) if primary["status"] == "ok" else None
    return StationarityComputeResult(
        "complete",
        None,
        {
            "eligibility_tier": "primary" if primary_payload is not None else "sensitivity",
            "primary": primary_payload,
            "sensitivity": [_published_segment(item) for item in sensitivity],
        },
        audit,
    )


__all__ = [
    "StationarityBundle",
    "StationarityComputeResult",
    "compute_stationarity",
    "stationarity_bundle",
]

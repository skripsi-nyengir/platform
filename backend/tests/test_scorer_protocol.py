from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta
import math

import pytest

from anomaly_worker.scorer import (
    CHANNELS,
    PreviewSimulatorScorer,
    ScoreBatch,
    ScoreBatchResult,
    ScorePoint,
    ScorerProtocolError,
    TemporalSemantics,
    validate_batch,
    validate_result,
)


ARCHIVE_SHA = "6c5a7ee8c248931bcc490cc114a3af55add8af82f976f58015ff7225dccce01a"


def batch(size: int = 2, *, forecast: bool = False) -> ScoreBatch:
    base = datetime(2026, 5, 1)
    contexts = tuple(
        tuple(base + timedelta(seconds=30 * (window + position)) for position in range(30))
        for window in range(size)
    )
    raw = tuple(
        tuple((25.0 + window, 60.0 + position / 100) for position in range(30))
        for window in range(size)
    )
    model = tuple(
        tuple((0.2 + window / 10, 0.4 + position / 100) for position in range(30))
        for window in range(size)
    )
    targets = tuple(
        context[-1] + (timedelta(seconds=30) if forecast else timedelta())
        for context in contexts
    )
    return ScoreBatch(
        model_version="preview-lstm-ae-v1",
        schema_version="b02-v1",
        channels=CHANNELS,
        raw_values=raw,
        model_values=model,
        context_ts=contexts,
        context_start_indices=tuple(range(size)),
        context_end_indices=tuple(index + 29 for index in range(size)),
        segment_ids=(0,) * size,
        eligible_window_ordinals=tuple(range(size)),
        target_ts=targets,
        target_raw_values=((26.0, 61.0),) * size if forecast else None,
        target_model_values=((0.3, 0.5),) * size if forecast else None,
    )


def test_preview_scorer_satisfies_immutable_context_end_contract() -> None:
    request = batch()
    with pytest.raises(FrozenInstanceError):
        request.model_version = "changed"  # type: ignore[misc]
    scorer = PreviewSimulatorScorer(ARCHIVE_SHA)
    result = scorer.score(request)
    assert len(result.points) == request.size
    assert tuple(point.score_ts for point in result.points) == request.target_ts
    assert all(math.isfinite(point.score) for point in result.points)


def test_next_target_contract_requires_future_target_values() -> None:
    forecast = batch(forecast=True)
    validate_batch(forecast, TemporalSemantics.NEXT_TARGET)
    result = ScoreBatchResult(
        tuple(ScorePoint(timestamp, 0.4) for timestamp in forecast.target_ts)
    )
    validate_result(forecast, result, TemporalSemantics.NEXT_TARGET)
    with pytest.raises(ScorerProtocolError, match="target_raw_values"):
        validate_batch(
            replace(forecast, target_raw_values=None),
            TemporalSemantics.NEXT_TARGET,
        )


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda value: replace(value, channels=("rh", "suhu")), "channel order"),
        (
            lambda value: replace(
                value, raw_values=((value.raw_values[0][:-1]),) + value.raw_values[1:]
            ),
            "shape",
        ),
        (
            lambda value: replace(
                value,
                model_values=(
                    ((float("nan"), 1.0),) + value.model_values[0][1:],
                )
                + value.model_values[1:],
            ),
            "finite",
        ),
        (
            lambda value: replace(
                value,
                model_values=(
                    ((1e100, 1.0),) + value.model_values[0][1:],
                )
                + value.model_values[1:],
            ),
            "float32",
        ),
        (
            lambda value: replace(value, target_ts=(value.target_ts[0] + timedelta(seconds=1),) + value.target_ts[1:]),
            "context-end",
        ),
        (
            lambda value: replace(value, eligible_window_ordinals=(1, 0)),
            "order",
        ),
    ],
)
def test_invalid_batch_is_rejected(mutate, message: str) -> None:
    with pytest.raises(ScorerProtocolError, match=message):
        validate_batch(mutate(batch()), TemporalSemantics.CONTEXT_END)


def test_wrong_count_timestamp_and_nonfinite_output_are_rejected() -> None:
    request = batch()
    wrong_count = ScoreBatchResult((ScorePoint(request.target_ts[0], 0.5),))
    wrong_timestamp = ScoreBatchResult(
        (
            ScorePoint(request.target_ts[0], 0.5),
            ScorePoint(request.target_ts[0], 0.5),
        )
    )
    nonfinite = ScoreBatchResult(
        (
            ScorePoint(request.target_ts[0], 0.5),
            ScorePoint(request.target_ts[1], float("inf")),
        )
    )
    for result in (wrong_count, wrong_timestamp, nonfinite):
        with pytest.raises(ScorerProtocolError):
            validate_result(request, result, TemporalSemantics.CONTEXT_END)


def test_threshold_comparison_is_not_part_of_scorer_contract() -> None:
    assert "threshold" not in ScoreBatch.__dataclass_fields__
    assert "threshold" not in ScoreBatchResult.__dataclass_fields__
    assert "provenance" not in ScoreBatch.__dataclass_fields__
    assert "is_anomaly" not in ScorePoint.__dataclass_fields__

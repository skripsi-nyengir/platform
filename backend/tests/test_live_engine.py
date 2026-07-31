from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from anomaly_worker.live_engine import (
    BoundaryReason,
    EpisodeState,
    WindowEngineState,
    WindowInput,
    acknowledge_alert,
    check_data_gap,
    close_episode,
    enqueue_input,
    evaluate_score,
    process_input,
    resolve_alert,
)


NOW = datetime(2040, 1, 1, tzinfo=timezone.utc)
PAIR_A = UUID(int=1)
PAIR_B = UUID(int=2)


def _input(
    index: int,
    *,
    at: datetime | None = None,
    pair: UUID = PAIR_A,
    activation_id: int = 1,
    continuity_epoch: int = 1,
) -> WindowInput:
    return WindowInput(
        received_at_utc=at or NOW + timedelta(seconds=index * 6),
        model_pair_id=pair,
        activation_id=activation_id,
        continuity_epoch=continuity_epoch,
        payload=index,
    )


def _open_episode(
    *, severity_score: float = 1.5, episode_id: UUID | None = None
) -> EpisodeState:
    transition = evaluate_score(
        EpisodeState(),
        score=severity_score,
        threshold=1.0,
        new_episode_id=episode_id or UUID(int=10),
    )
    assert transition.opened
    return transition.state


def test_tenth_input_emits_first_window_then_every_input_uses_stride_one() -> None:
    state = WindowEngineState()

    for index in range(9):
        transition = process_input(state, _input(index))
        state = transition.state
        assert transition.window is None

    tenth = process_input(state, _input(9))
    assert [item.payload for item in tenth.window or ()] == list(range(10))

    eleventh = process_input(tenth.state, _input(10))
    assert [item.payload for item in eleventh.window or ()] == list(range(1, 11))


def test_exactly_twelve_seconds_is_continuous_but_more_resets_for_data_gap() -> None:
    state = WindowEngineState()
    first = process_input(state, _input(0, at=NOW))
    exact = process_input(first.state, _input(1, at=NOW + timedelta(seconds=12)))

    assert exact.reset_reason is None
    assert len(exact.state.window) == 2

    gap = process_input(
        exact.state,
        _input(2, at=NOW + timedelta(seconds=24, microseconds=1)),
    )

    assert gap.reset_reason == "data_gap"
    assert gap.window is None
    assert gap.state.window == (
        _input(2, at=NOW + timedelta(seconds=24, microseconds=1)),
    )


@pytest.mark.parametrize(
    ("pair", "activation_id"),
    [(PAIR_B, 1), (PAIR_A, 2)],
)
def test_model_scaler_pair_or_reactivation_change_resets_window(
    pair: UUID, activation_id: int
) -> None:
    state = process_input(WindowEngineState(), _input(0)).state

    changed = process_input(
        state,
        _input(1, pair=pair, activation_id=activation_id),
    )

    assert changed.reset_reason == "model_change"
    assert len(changed.state.window) == 1


def test_pending_capacity_drops_oldest_resets_window_and_counts_every_drop() -> None:
    state = WindowEngineState(window=(_input(0),))
    for index in range(100):
        state = enqueue_input(state, _input(index)).state

    first_drop = enqueue_input(state, _input(100))

    assert first_drop.reset_reason == "overload"
    assert first_drop.dropped == 1
    assert first_drop.state.dropped_count == 1
    assert first_drop.state.window == ()
    assert len(first_drop.state.pending) == 100
    assert first_drop.state.pending[0].payload == 1
    assert first_drop.state.pending[-1].payload == 100

    second_drop = enqueue_input(first_drop.state, _input(101))
    assert second_drop.dropped == 1
    assert second_drop.state.dropped_count == 2
    assert second_drop.state.pending[0].payload == 2


@pytest.mark.parametrize(
    ("score", "expected"),
    [(1.0, None), (1.000001, "warning"), (2.0, "warning"), (2.000001, "critical")],
)
def test_first_anomaly_opens_episode_at_exact_severity_boundaries(
    score: float, expected: str | None
) -> None:
    transition = evaluate_score(
        EpisodeState(),
        score=score,
        threshold=1.0,
        new_episode_id=UUID(int=10),
    )

    assert transition.opened is (expected is not None)
    if expected is None:
        assert transition.state.episode is None
    else:
        assert transition.state.episode is not None
        assert transition.state.episode.severity == expected
        assert transition.state.episode.alert_status == "detected"


def test_open_episode_escalates_to_critical_but_never_lowers_severity() -> None:
    warning = _open_episode()
    critical = evaluate_score(
        warning,
        score=2.5,
        threshold=1.0,
        new_episode_id=UUID(int=11),
    ).state
    lower = evaluate_score(
        critical,
        score=1.1,
        threshold=1.0,
        new_episode_id=UUID(int=12),
    ).state

    assert critical.episode is not None
    assert lower.episode is not None
    assert critical.episode.severity == lower.episode.severity == "critical"


def test_three_consecutive_normal_scores_close_for_recovery() -> None:
    state = _open_episode()

    first = evaluate_score(state, score=0.5, threshold=1.0)
    second = evaluate_score(first.state, score=0.5, threshold=1.0)
    third = evaluate_score(second.state, score=0.5, threshold=1.0)

    assert first.state.episode is not None
    assert second.state.episode is not None
    assert first.state.episode.consecutive_normal == 1
    assert second.state.episode.consecutive_normal == 2
    assert third.closed
    assert third.state.episode is not None
    assert third.state.episode.status == "closed"
    assert third.state.episode.close_reason == "normal_recovery"


def test_anomaly_resets_the_consecutive_normal_recovery_count() -> None:
    state = _open_episode()
    state = evaluate_score(state, score=0.5, threshold=1.0).state
    state = evaluate_score(state, score=1.5, threshold=1.0).state

    assert state.episode is not None
    assert state.episode.consecutive_normal == 0


@pytest.mark.parametrize(
    "reason",
    ["data_gap", "model_change", "overload", "startup", "lease_takeover"],
)
def test_technical_boundary_closes_open_episode_immediately(
    reason: BoundaryReason,
) -> None:
    transition = close_episode(_open_episode(), reason)

    assert transition.closed
    assert transition.state.episode is not None
    assert transition.state.episode.status == "closed"
    assert transition.state.episode.close_reason == reason


def test_simultaneous_technical_closures_use_fixed_precedence_over_recovery() -> None:
    transition = close_episode(
        _open_episode(),
        ("data_gap", "model_change", "overload"),
    )

    assert transition.state.episode is not None
    assert transition.state.episode.close_reason == "overload"


def test_full_technical_close_precedence_is_stable() -> None:
    reasons: tuple[BoundaryReason, ...] = (
        "data_gap",
        "model_change",
        "overload",
        "startup",
        "lease_takeover",
    )

    for highest_index, expected in enumerate(reasons):
        transition = close_episode(_open_episode(), reasons[: highest_index + 1])
        assert transition.state.episode is not None
        assert transition.state.episode.close_reason == expected


def test_technical_close_preempts_simultaneous_third_normal_recovery() -> None:
    state = _open_episode()
    state = evaluate_score(state, score=0.5, threshold=1.0).state
    state = evaluate_score(state, score=0.5, threshold=1.0).state

    transition = evaluate_score(
        state,
        score=0.5,
        threshold=1.0,
        technical_reasons=("data_gap", "model_change"),
    )

    assert transition.closed
    assert transition.state.episode is not None
    assert transition.state.episode.close_reason == "model_change"


def test_watchdog_closes_only_after_twelve_seconds_and_is_idempotent() -> None:
    state = _open_episode()
    at_limit = check_data_gap(
        state, last_received_at_utc=NOW, now=NOW + timedelta(seconds=12)
    )
    after_limit = check_data_gap(
        at_limit.state,
        last_received_at_utc=NOW,
        now=NOW + timedelta(seconds=12, microseconds=1),
    )
    repeated = check_data_gap(
        after_limit.state,
        last_received_at_utc=NOW,
        now=NOW + timedelta(seconds=20),
    )

    assert not at_limit.closed
    assert after_limit.closed
    assert after_limit.state.episode is not None
    assert after_limit.state.episode.close_reason == "data_gap"
    assert not repeated.closed
    assert repeated.state == after_limit.state


def test_anomaly_after_close_opens_a_separate_episode() -> None:
    first_id = UUID(int=10)
    second_id = UUID(int=11)
    closed = close_episode(_open_episode(episode_id=first_id), "data_gap").state

    next_episode = evaluate_score(
        closed,
        score=1.5,
        threshold=1.0,
        new_episode_id=second_id,
    )

    assert next_episode.opened
    assert next_episode.state.episode is not None
    assert next_episode.state.episode.live_episode_id == second_id
    assert next_episode.state.episode.live_episode_id != first_id


def test_technical_close_keeps_alert_lifecycle_separate() -> None:
    open_state = _open_episode()
    acknowledged = acknowledge_alert(open_state)

    assert acknowledged.command_accepted
    assert acknowledged.state.episode is not None
    assert acknowledged.state.episode.alert_status == "acknowledged"
    assert not resolve_alert(acknowledged.state).command_accepted

    closed = close_episode(acknowledged.state, "model_change")
    assert closed.state.episode is not None
    assert closed.state.episode.alert_status == "acknowledged"

    resolved = resolve_alert(closed.state)
    assert resolved.command_accepted
    assert resolved.state.episode is not None
    assert resolved.state.episode.alert_status == "resolved"


def test_operator_commands_are_idempotent() -> None:
    open_state = _open_episode()

    rejected = resolve_alert(open_state)
    rejected_again = resolve_alert(rejected.state)
    acknowledged = acknowledge_alert(rejected_again.state)
    acknowledged_again = acknowledge_alert(acknowledged.state)
    closed = close_episode(acknowledged_again.state, "data_gap")
    resolved = resolve_alert(closed.state)
    resolved_again = resolve_alert(resolved.state)

    assert not rejected.command_accepted
    assert rejected_again == rejected
    assert acknowledged.command_accepted
    assert acknowledged_again.command_accepted
    assert acknowledged_again.state == acknowledged.state
    assert resolved.command_accepted
    assert resolved_again.command_accepted
    assert resolved_again.state == resolved.state


def test_window_input_defensively_snapshots_mutable_payload() -> None:
    samples = [2, 3]
    payload: list[object] = [1, {"samples": samples}]
    item = WindowInput(
        received_at_utc=NOW,
        model_pair_id=PAIR_A,
        activation_id=1,
        continuity_epoch=1,
        payload=payload,
    )
    transition = process_input(WindowEngineState(), item)

    payload.append(4)
    samples.append(5)

    assert transition.state.window[0].payload == (1, (("samples", (2, 3)),))


def test_state_objects_are_immutable_and_transitions_do_not_modify_inputs() -> None:
    window = WindowEngineState()
    episode = _open_episode()

    _ = process_input(window, _input(0))
    _ = evaluate_score(episode, score=2.5, threshold=1.0)

    assert window == WindowEngineState()
    assert episode.episode is not None
    assert episode.episode.severity == "warning"
    with pytest.raises(FrozenInstanceError):
        setattr(window, "dropped_count", 1)


@pytest.mark.parametrize(("score", "threshold"), [(float("nan"), 1.0), (1.0, 0.0)])
def test_invalid_score_inputs_are_rejected(score: float, threshold: float) -> None:
    with pytest.raises(ValueError):
        _ = evaluate_score(EpisodeState(), score=score, threshold=threshold)

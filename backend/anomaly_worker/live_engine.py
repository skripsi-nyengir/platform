from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
import math
from typing import Literal, cast
from uuid import UUID


WINDOW_SIZE = 10
PENDING_CAPACITY = 100
MAX_GAP = timedelta(seconds=12)

BoundaryReason = Literal[
    "startup", "data_gap", "model_change", "overload", "lease_takeover"
]
CloseReason = Literal[
    "normal_recovery",
    "startup",
    "data_gap",
    "model_change",
    "overload",
    "lease_takeover",
]
Severity = Literal["warning", "critical"]
EpisodeStatus = Literal["open", "closed"]
AlertStatus = Literal["detected", "acknowledged", "resolved"]

_BOUNDARY_PRECEDENCE: tuple[BoundaryReason, ...] = (
    "data_gap",
    "model_change",
    "overload",
    "startup",
    "lease_takeover",
)


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("live engine timestamps must be timezone-aware")


def _freeze_payload(value: object) -> object:
    if value is None or isinstance(
        value, (bool, int, float, str, bytes, UUID, datetime)
    ):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        return tuple(
            (_freeze_payload(key), _freeze_payload(item))
            for key, item in mapping.items()
        )
    if isinstance(value, (list, tuple)):
        sequence = cast(list[object] | tuple[object, ...], value)
        return tuple(_freeze_payload(item) for item in sequence)
    if isinstance(value, (set, frozenset)):
        collection = cast(set[object] | frozenset[object], value)
        return frozenset(_freeze_payload(item) for item in collection)
    raise TypeError("live window payload must contain immutable snapshot values")


@dataclass(frozen=True, slots=True)
class WindowInput:
    received_at_utc: datetime
    model_pair_id: UUID
    activation_id: int
    continuity_epoch: int
    payload: object

    def __post_init__(self) -> None:
        _require_aware(self.received_at_utc)
        object.__setattr__(self, "payload", _freeze_payload(self.payload))


@dataclass(frozen=True, slots=True)
class WindowEngineState:
    pending: tuple[WindowInput, ...] = ()
    window: tuple[WindowInput, ...] = ()
    dropped_count: int = 0

    def __post_init__(self) -> None:
        if len(self.pending) > PENDING_CAPACITY:
            raise ValueError("pending live input capacity exceeded")
        if len(self.window) > WINDOW_SIZE:
            raise ValueError("live scoring window capacity exceeded")
        if self.dropped_count < 0:
            raise ValueError("dropped_count cannot be negative")


@dataclass(frozen=True, slots=True)
class WindowTransition:
    state: WindowEngineState
    window: tuple[WindowInput, ...] | None = None
    reset_reason: BoundaryReason | None = None
    dropped: int = 0


def enqueue_input(state: WindowEngineState, item: WindowInput) -> WindowTransition:
    if len(state.pending) < PENDING_CAPACITY:
        return WindowTransition(state=replace(state, pending=(*state.pending, item)))
    return WindowTransition(
        state=WindowEngineState(
            pending=(*state.pending[1:], item),
            window=(),
            dropped_count=state.dropped_count + 1,
        ),
        reset_reason="overload",
        dropped=1,
    )


def process_input(state: WindowEngineState, item: WindowInput) -> WindowTransition:
    reset_reason: BoundaryReason | None = None
    current = state.window
    if current:
        previous = current[-1]
        if (
            item.model_pair_id != previous.model_pair_id
            or item.activation_id != previous.activation_id
        ):
            reset_reason = "model_change"
        elif item.continuity_epoch != previous.continuity_epoch:
            reset_reason = "startup"
        elif item.received_at_utc - previous.received_at_utc > MAX_GAP:
            reset_reason = "data_gap"

    samples = deque(() if reset_reason is not None else current, maxlen=WINDOW_SIZE)
    samples.append(item)
    next_window = tuple(samples)
    next_state = replace(state, window=next_window)
    return WindowTransition(
        state=next_state,
        window=next_window if len(next_window) == WINDOW_SIZE else None,
        reset_reason=reset_reason,
    )


@dataclass(frozen=True, slots=True)
class Episode:
    live_episode_id: UUID
    status: EpisodeStatus
    severity: Severity
    consecutive_normal: int = 0
    close_reason: CloseReason | None = None
    alert_status: AlertStatus = "detected"


@dataclass(frozen=True, slots=True)
class EpisodeState:
    episode: Episode | None = None


@dataclass(frozen=True, slots=True)
class EpisodeTransition:
    state: EpisodeState
    opened: bool = False
    closed: bool = False
    command_accepted: bool = False


def _severity(score: float, threshold: float) -> Severity | None:
    if not math.isfinite(score):
        raise ValueError("score must be finite")
    if not math.isfinite(threshold) or threshold <= 0:
        raise ValueError("threshold must be finite and greater than zero")
    ratio = score / threshold
    if ratio > 2:
        return "critical"
    if ratio > 1:
        return "warning"
    return None


def evaluate_score(
    state: EpisodeState,
    *,
    score: float,
    threshold: float,
    new_episode_id: UUID | None = None,
    technical_reasons: tuple[BoundaryReason, ...] = (),
) -> EpisodeTransition:
    if technical_reasons:
        return close_episode(state, technical_reasons)
    severity = _severity(score, threshold)
    episode = state.episode
    if episode is None or episode.status == "closed":
        if severity is None:
            return EpisodeTransition(state=state)
        if new_episode_id is None:
            raise ValueError("new_episode_id is required to open an episode")
        if episode is not None and new_episode_id == episode.live_episode_id:
            raise ValueError("a new anomaly requires a distinct live_episode_id")
        return EpisodeTransition(
            state=EpisodeState(
                Episode(
                    live_episode_id=new_episode_id,
                    status="open",
                    severity=severity,
                )
            ),
            opened=True,
        )

    if severity is not None:
        next_severity: Severity = (
            "critical"
            if episode.severity == "critical" or severity == "critical"
            else "warning"
        )
        return EpisodeTransition(
            state=EpisodeState(
                replace(
                    episode,
                    severity=next_severity,
                    consecutive_normal=0,
                )
            )
        )

    consecutive_normal = episode.consecutive_normal + 1
    if consecutive_normal < 3:
        return EpisodeTransition(
            state=EpisodeState(replace(episode, consecutive_normal=consecutive_normal))
        )
    return EpisodeTransition(
        state=EpisodeState(
            replace(
                episode,
                status="closed",
                consecutive_normal=3,
                close_reason="normal_recovery",
            )
        ),
        closed=True,
    )


def close_episode(
    state: EpisodeState,
    reasons: BoundaryReason | tuple[BoundaryReason, ...],
) -> EpisodeTransition:
    episode = state.episode
    if episode is None or episode.status == "closed":
        return EpisodeTransition(state=state)
    candidates = (reasons,) if isinstance(reasons, str) else reasons
    if not candidates:
        raise ValueError("at least one close reason is required")
    reason = max(candidates, key=_BOUNDARY_PRECEDENCE.index)
    return EpisodeTransition(
        state=EpisodeState(replace(episode, status="closed", close_reason=reason)),
        closed=True,
    )


def check_data_gap(
    state: EpisodeState,
    *,
    last_received_at_utc: datetime,
    now: datetime,
) -> EpisodeTransition:
    _require_aware(last_received_at_utc)
    _require_aware(now)
    if now - last_received_at_utc <= MAX_GAP:
        return EpisodeTransition(state=state)
    return close_episode(state, "data_gap")


def acknowledge_alert(state: EpisodeState) -> EpisodeTransition:
    episode = state.episode
    if episode is None or episode.alert_status == "resolved":
        return EpisodeTransition(state=state)
    if episode.alert_status == "acknowledged":
        return EpisodeTransition(state=state, command_accepted=True)
    return EpisodeTransition(
        state=EpisodeState(replace(episode, alert_status="acknowledged")),
        command_accepted=True,
    )


def resolve_alert(state: EpisodeState) -> EpisodeTransition:
    episode = state.episode
    if episode is None or episode.status == "open":
        return EpisodeTransition(state=state)
    if episode.alert_status == "detected":
        return EpisodeTransition(state=state)
    if episode.alert_status == "resolved":
        return EpisodeTransition(state=state, command_accepted=True)
    return EpisodeTransition(
        state=EpisodeState(replace(episode, alert_status="resolved")),
        command_accepted=True,
    )

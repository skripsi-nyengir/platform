from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypedDict

BIN_SIZE = 51


@dataclass(frozen=True, slots=True)
class ScoredRow:
    score_ts: str
    score: float
    is_anomaly: bool
    threshold: float
    segment_id: int


@dataclass(frozen=True, slots=True)
class CompletedBin:
    segment_id: int
    bin_ordinal: int
    start_score_ts: str
    end_score_ts: str
    scored_timestamp_count: int
    is_alert: bool
    candidate_alert_count: int
    first_alert_ts: str | None
    last_alert_ts: str | None
    peak_score: float
    latest_score: float
    threshold: float


class OpenBin(TypedDict):
    segment_id: int
    bin_ordinal: int
    count: int
    start_score_ts: str
    is_alert: bool
    candidate_alert_count: int
    first_alert_ts: str | None
    last_alert_ts: str | None
    peak_score: float
    latest_score: float
    threshold: float


class BinState(TypedDict):
    segment_id: int | None
    next_ordinal: int
    open_bin: OpenBin | None


def default_bin_state() -> BinState:
    return {"segment_id": None, "next_ordinal": 0, "open_bin": None}


def accumulate_bins(
    state: BinState, rows: Sequence[ScoredRow]
) -> tuple[list[CompletedBin], BinState]:
    segment_id = state["segment_id"]
    next_ordinal = state["next_ordinal"]
    open_bin = state["open_bin"]
    completed: list[CompletedBin] = []

    for row in rows:
        if segment_id != row.segment_id:
            segment_id = row.segment_id
            next_ordinal = 0
            open_bin = None
        if open_bin is None:
            open_bin = OpenBin(
                segment_id=row.segment_id,
                bin_ordinal=next_ordinal,
                count=0,
                start_score_ts=row.score_ts,
                is_alert=False,
                candidate_alert_count=0,
                first_alert_ts=None,
                last_alert_ts=None,
                peak_score=row.score,
                latest_score=row.score,
                threshold=row.threshold,
            )
        open_bin["count"] += 1
        open_bin["latest_score"] = row.score
        open_bin["threshold"] = row.threshold
        if row.score > open_bin["peak_score"]:
            open_bin["peak_score"] = row.score
        if row.is_anomaly:
            open_bin["is_alert"] = True
            open_bin["candidate_alert_count"] += 1
            if open_bin["first_alert_ts"] is None:
                open_bin["first_alert_ts"] = row.score_ts
            open_bin["last_alert_ts"] = row.score_ts
        if open_bin["count"] == BIN_SIZE:
            completed.append(
                CompletedBin(
                    segment_id=open_bin["segment_id"],
                    bin_ordinal=open_bin["bin_ordinal"],
                    start_score_ts=open_bin["start_score_ts"],
                    end_score_ts=row.score_ts,
                    scored_timestamp_count=BIN_SIZE,
                    is_alert=open_bin["is_alert"],
                    candidate_alert_count=open_bin["candidate_alert_count"],
                    first_alert_ts=open_bin["first_alert_ts"],
                    last_alert_ts=open_bin["last_alert_ts"],
                    peak_score=open_bin["peak_score"],
                    latest_score=open_bin["latest_score"],
                    threshold=open_bin["threshold"],
                )
            )
            next_ordinal = open_bin["bin_ordinal"] + 1
            open_bin = None

    return completed, BinState(
        segment_id=segment_id,
        next_ordinal=next_ordinal,
        open_bin=open_bin,
    )

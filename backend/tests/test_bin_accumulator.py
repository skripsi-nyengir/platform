from datetime import datetime, timedelta

from anomaly_worker.bin_accumulator import (
    BIN_SIZE,
    ScoredRow,
    accumulate_bins,
    default_bin_state,
)

_BASE = datetime(2026, 5, 31, 23, 0, 0)


def _ts(index: int) -> str:
    return (_BASE + timedelta(seconds=index * 3)).isoformat(timespec="seconds")


def _row(
    index: int,
    *,
    anomaly: bool = False,
    segment_id: int = 0,
    threshold: float = 1.0,
) -> ScoredRow:
    return ScoredRow(
        score_ts=_ts(index),
        score=1.5 if anomaly else 0.5,
        is_anomaly=anomaly,
        threshold=threshold,
        segment_id=segment_id,
    )


def _normal_bin(start: int = 0, *, segment_id: int = 0) -> list[ScoredRow]:
    return [_row(start + i, segment_id=segment_id) for i in range(BIN_SIZE)]


def test_fifty_one_normal_scores_form_one_normal_bin() -> None:
    bins, state = accumulate_bins(default_bin_state(), _normal_bin())
    assert len(bins) == 1
    published = bins[0]
    assert published.scored_timestamp_count == 51
    assert published.is_alert is False
    assert published.candidate_alert_count == 0
    assert published.first_alert_ts is None
    assert published.last_alert_ts is None
    assert published.start_score_ts == _ts(0)
    assert published.end_score_ts == _ts(50)
    assert published.bin_ordinal == 0
    assert state["open_bin"] is None
    assert state["next_ordinal"] == 1


def test_single_candidate_alert_makes_bin_alert() -> None:
    rows = _normal_bin()
    rows[25] = _row(25, anomaly=True)
    bins, _ = accumulate_bins(default_bin_state(), rows)
    published = bins[0]
    assert published.is_alert is True
    assert published.candidate_alert_count == 1
    assert published.first_alert_ts == _ts(25)
    assert published.last_alert_ts == _ts(25)


def test_many_candidate_alerts_tracked() -> None:
    rows = _normal_bin()
    rows[10] = _row(10, anomaly=True)
    rows[20] = _row(20, anomaly=True)
    rows[40] = _row(40, anomaly=True)
    bins, _ = accumulate_bins(default_bin_state(), rows)
    published = bins[0]
    assert published.candidate_alert_count == 3
    assert published.first_alert_ts == _ts(10)
    assert published.last_alert_ts == _ts(40)


def test_candidate_alert_at_bin_boundaries_counted() -> None:
    rows = _normal_bin()
    rows[0] = _row(0, anomaly=True)
    rows[50] = _row(50, anomaly=True)
    bins, _ = accumulate_bins(default_bin_state(), rows)
    published = bins[0]
    assert published.candidate_alert_count == 2
    assert published.first_alert_ts == _ts(0)
    assert published.last_alert_ts == _ts(50)


def test_gap_resets_partial_and_ordinal() -> None:
    rows = _normal_bin(0, segment_id=0)
    rows += [_row(51 + i, segment_id=0) for i in range(10)]
    rows += _normal_bin(100, segment_id=1)
    bins, state = accumulate_bins(default_bin_state(), rows)
    assert len(bins) == 2
    assert bins[0].segment_id == 0
    assert bins[0].bin_ordinal == 0
    assert bins[1].segment_id == 1
    assert bins[1].bin_ordinal == 0
    assert state["open_bin"] is None


def test_partial_bin_not_emitted_and_persists_in_state() -> None:
    rows = [_row(i) for i in range(30)]
    bins, state = accumulate_bins(default_bin_state(), rows)
    assert bins == []
    open_bin = state["open_bin"]
    assert open_bin is not None
    assert open_bin["count"] == 30
    assert open_bin["bin_ordinal"] == 0


def test_split_batches_equal_single_pass() -> None:
    rows = _normal_bin(0) + _normal_bin(51)
    rows[70] = _row(70, anomaly=True)
    single_bins, single_state = accumulate_bins(default_bin_state(), rows)
    part1, state1 = accumulate_bins(default_bin_state(), rows[:60])
    part2, state2 = accumulate_bins(state1, rows[60:])
    assert single_bins == part1 + part2
    assert single_state == state2


def test_sequential_bins_increment_ordinal() -> None:
    rows = _normal_bin(0) + _normal_bin(51)
    bins, state = accumulate_bins(default_bin_state(), rows)
    assert [published.bin_ordinal for published in bins] == [0, 1]
    assert state["next_ordinal"] == 2

from datetime import datetime, timedelta

from anomaly_worker.import_transform import (
    TARGET_SOURCE_UUID,
    StagingRow,
    transform_staging_rows,
)


def rows_at(
    timestamp: datetime,
    suhu: float = 25.0,
    rh: float = 60.0,
) -> list[StagingRow]:
    return [
        StagingRow(TARGET_SOURCE_UUID, 0, suhu, timestamp),
        StagingRow(TARGET_SOURCE_UUID, 1, rh, timestamp),
    ]


def test_transform_oracle_covers_filters_segments_splits_and_scaler() -> None:
    feb = datetime(2026, 2, 1)
    validation = datetime(2026, 5, 10)
    test = datetime(2026, 5, 20)
    crop_last = datetime(2026, 5, 31, 23, 59, 59)
    staged = [
        *rows_at(feb, 20, 40),
        StagingRow(TARGET_SOURCE_UUID, 0, 20, feb),  # identical duplicate
        StagingRow(TARGET_SOURCE_UUID, 2, 999, feb),  # counted/ignored
        *rows_at(feb + timedelta(seconds=600), 30, 70),  # same segment
        *rows_at(feb + timedelta(seconds=1201), 22, 45),  # gap 601
        *rows_at(validation, 23, 50),
        *rows_at(test, 24, 55),
        *rows_at(crop_last, 25, 60),
        *rows_at(datetime(2026, 6, 1), 26, 61),  # half-open exclusion
        StagingRow("another-device", 0, 10, feb),
        StagingRow(TARGET_SOURCE_UUID, 0, 25, feb + timedelta(days=1)),
        StagingRow(TARGET_SOURCE_UUID, 1, 50, feb + timedelta(days=1)),
        StagingRow(TARGET_SOURCE_UUID, 1, 51, feb + timedelta(days=1)),  # conflict
        StagingRow(TARGET_SOURCE_UUID, 0, 25, feb + timedelta(days=2)),  # incomplete
        *rows_at(feb + timedelta(days=3), 0, 40),
        StagingRow(TARGET_SOURCE_UUID, 9, 12, feb),
    ]

    result = transform_staging_rows(reversed(staged))
    assert [
        (
            point.timestamp,
            point.suhu,
            point.rh,
            point.corpus_index,
            point.segment_id,
            point.dataset_split,
        )
        for point in result.points
    ] == [
        (feb, 20.0, 40.0, 0, 0, "train"),
        (feb + timedelta(seconds=600), 30.0, 70.0, 1, 0, "train"),
        (feb + timedelta(seconds=1201), 22.0, 45.0, 2, 1, "train"),
        (validation, 23.0, 50.0, 3, 2, "validation"),
        (test, 24.0, 55.0, 4, 3, "test"),
        (crop_last, 25.0, 60.0, 5, 4, "test"),
    ]
    assert result.scaler["suhu"].minimum == 20
    assert result.scaler["suhu"].maximum == 30
    assert result.scaler["rh"].minimum == 40
    assert result.scaler["rh"].maximum == 70
    assert result.ignored_index_count == 1
    assert result.rejection_counts == {
        "wrong_device": 1,
        "outside_crop": 2,
        "unsupported_index": 1,
        "duplicate_identical": 1,
        "duplicate_conflict": 1,
        "incomplete_pair": 1,
        "invalid_or_sentinel": 1,
        "suspect_buffer": 0,
    }


def test_suspect_episode_merge_and_inclusive_buffers() -> None:
    base = datetime(2026, 3, 1, 12)
    staged = [
        *rows_at(base - timedelta(seconds=601), 20, 40),  # survives
        *rows_at(base - timedelta(seconds=600), 21, 41),  # removed boundary
        *rows_at(base, 36, 50),  # suspect
        *rows_at(base + timedelta(seconds=600), 25, 81),  # merged suspect
        *rows_at(base + timedelta(seconds=1200), 22, 42),  # removed boundary
        *rows_at(base + timedelta(seconds=1201), 23, 43),  # survives
        *rows_at(base + timedelta(seconds=1801), 36, 50),  # new episode at 601
        *rows_at(base + timedelta(seconds=2401), 24, 44),  # removed boundary
        *rows_at(base + timedelta(seconds=2402), 25, 45),  # survives
    ]
    result = transform_staging_rows(staged)
    assert [point.timestamp for point in result.points] == [
        base - timedelta(seconds=601),
        base + timedelta(seconds=2402),
    ]
    assert result.rejection_counts["suspect_buffer"] == 7
    assert [point.segment_id for point in result.points] == [0, 1]


def test_all_invalid_and_sentinel_boundaries_are_rejected() -> None:
    base = datetime(2026, 4, 1)
    staged = [*rows_at(base, 20, 40)]
    invalid_pairs = (
        (0, 40),
        (-1, 40),
        (200, 40),
        (201, 40),
        (20, 0),
        (20, -1),
        (20, 101),
        (20, 200),
        (20, 201),
    )
    for offset, (suhu, rh) in enumerate(invalid_pairs, start=1):
        staged.extend(rows_at(base + timedelta(days=offset), suhu, rh))

    result = transform_staging_rows(staged)
    assert [point.timestamp for point in result.points] == [base]
    assert result.rejection_counts["invalid_or_sentinel"] == len(invalid_pairs)


def test_order_and_duplicate_rows_do_not_change_corpus_identity() -> None:
    base = datetime(2026, 4, 1)
    staged = [
        *rows_at(base, 20, 40),
        *rows_at(base + timedelta(seconds=30), 21, 41),
        *rows_at(base + timedelta(seconds=60), 22, 42),
    ]
    duplicated = staged + [staged[0], staged[1]]
    forward = transform_staging_rows(duplicated)
    reverse = transform_staging_rows(reversed(duplicated))
    assert forward.points == reverse.points
    assert forward.scaler == reverse.scaler

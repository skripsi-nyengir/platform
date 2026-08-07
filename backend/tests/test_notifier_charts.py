from datetime import datetime, timedelta
import struct

import pytest

from anomaly_backend.sql.notifications import ScorePoint, TelemetryPoint
from anomaly_worker.notifier_charts import (
    EmptyChartError,
    chart_window,
    score_chart,
    telemetry_chart,
)


BASE = datetime(2026, 8, 8, 1, 0, 0)
THRESHOLD = 2.657e-4


def _png_size(image: bytes) -> tuple[int, int]:
    # The IHDR chunk starts at byte 16 and carries width and height as big-endian
    # unsigned longs. Reading it proves the bytes really are a decodable image.
    assert image[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", image[16:24])
    return width, height


def _scores(count: int = 40) -> list[ScorePoint]:
    return [
        ScorePoint(
            score_ts=BASE + timedelta(seconds=10 * index),
            score=THRESHOLD * (2.0 if 10 <= index <= 20 else 0.4),
            threshold=THRESHOLD,
        )
        for index in range(count)
    ]


def _telemetry(count: int = 40) -> list[TelemetryPoint]:
    return [
        TelemetryPoint(
            received_ts=BASE + timedelta(seconds=10 * index),
            temperature_c=27.0 + (20.0 if 10 <= index <= 20 else 0.0),
            relative_humidity_pct=60.0 - (30.0 if 10 <= index <= 20 else 0.0),
        )
        for index in range(count)
    ]


def test_window_pads_both_sides_of_a_closed_episode() -> None:
    started = BASE + timedelta(minutes=10)
    ended = BASE + timedelta(minutes=20)

    window_start, window_end = chart_window(
        started, ended, margin_minutes=15, fallback_end=BASE
    )

    assert window_start == started - timedelta(minutes=15)
    assert window_end == ended + timedelta(minutes=15)


def test_window_of_an_open_episode_extends_past_the_fallback() -> None:
    started = BASE + timedelta(minutes=10)
    fallback = BASE + timedelta(minutes=25)

    _, window_end = chart_window(
        started, None, margin_minutes=5, fallback_end=fallback
    )

    # An open episode has no end, so the window has to reach past "now" instead.
    assert window_end == fallback + timedelta(minutes=5)


def test_score_chart_renders_a_decodable_image() -> None:
    image = score_chart(
        _scores(),
        started_score_ts=BASE + timedelta(seconds=100),
        ended_score_ts=BASE + timedelta(seconds=200),
        window_end=BASE + timedelta(seconds=400),
    )

    width, height = _png_size(image)
    assert width > 600 and height > 300
    assert len(image) > 5_000


def test_telemetry_chart_renders_a_decodable_image() -> None:
    image = telemetry_chart(
        _telemetry(),
        started_score_ts=BASE + timedelta(seconds=100),
        ended_score_ts=BASE + timedelta(seconds=200),
        window_end=BASE + timedelta(seconds=400),
    )

    width, height = _png_size(image)
    assert width > 600 and height > 300


def test_the_two_charts_are_different_images() -> None:
    # They are uploaded as separate attachments; rendering the same picture twice
    # would be a silent regression the size assertions above would not catch.
    span = {
        "started_score_ts": BASE + timedelta(seconds=100),
        "ended_score_ts": BASE + timedelta(seconds=200),
        "window_end": BASE + timedelta(seconds=400),
    }
    assert score_chart(_scores(), **span) != telemetry_chart(_telemetry(), **span)


def test_an_open_episode_renders_without_an_end_timestamp() -> None:
    image = score_chart(
        _scores(),
        started_score_ts=BASE + timedelta(seconds=100),
        ended_score_ts=None,
        window_end=BASE + timedelta(seconds=400),
    )

    assert _png_size(image)[0] > 600


@pytest.mark.parametrize("render", [score_chart, telemetry_chart])
def test_empty_data_refuses_rather_than_uploading_a_blank_image(
    render: object,
) -> None:
    with pytest.raises(EmptyChartError):
        _ = render(  # pyright: ignore[reportCallIssue]
            [],
            started_score_ts=BASE,
            ended_score_ts=None,
            window_end=BASE + timedelta(minutes=1),
        )

"""Chart rendering for Slack alert attachments.

Two separate images per notification rather than one stacked figure: the score chart
answers "why did the model decide this", the telemetry chart answers "what did the
sensor actually read", and Slack shows both at full width when they are separate
files.
"""

from datetime import datetime, timedelta
from io import BytesIO

import matplotlib

# Selected before pyplot is imported. Without it matplotlib looks for a display and
# fails inside the container.
matplotlib.use("Agg")

import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from anomaly_backend.sql.notifications import ScorePoint, TelemetryPoint  # noqa: E402


_FIGURE_SIZE = (10.0, 4.0)
_DPI = 130
_EPISODE_FILL = "#FF6B6B"
_SCORE_LINE = "#2563EB"
_THRESHOLD_LINE = "#C9374C"
_TEMPERATURE_LINE = "#C9374C"
_HUMIDITY_LINE = "#2563EB"


class EmptyChartError(ValueError):
    """Raised when there is nothing to plot, so a blank image is never uploaded."""


def chart_window(
    started_score_ts: datetime,
    ended_score_ts: datetime | None,
    *,
    margin_minutes: int,
    fallback_end: datetime,
) -> tuple[datetime, datetime]:
    """Episode span padded on both sides so the surrounding condition is visible."""
    margin = timedelta(minutes=margin_minutes)
    end = ended_score_ts if ended_score_ts is not None else fallback_end
    return started_score_ts - margin, end + margin


def _as_numbers(values: list[datetime]) -> list[float]:
    # matplotlib's own float date domain. Passing datetimes works at runtime but its
    # type stubs only accept numbers, and this repository runs pyright clean.
    return [float(mdates.date2num(value)) for value in values]


def _finish(figure: Figure) -> bytes:
    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=_DPI, bbox_inches="tight")
    plt.close(figure)
    return buffer.getvalue()


def _time_axis(axes: Axes) -> None:
    locator = mdates.AutoDateLocator()
    axes.xaxis.set_major_locator(locator)
    axes.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    axes.set_xlabel("UTC")
    axes.grid(True, axis="y", alpha=0.25)
    for spine in ("top", "right"):
        axes.spines[spine].set_visible(False)


def _mark_episode(
    axes: Axes, started: datetime, ended: datetime | None, fallback_end: datetime
) -> None:
    start_number, end_number = _as_numbers(
        [started, ended if ended is not None else fallback_end]
    )
    _ = axes.axvspan(
        start_number,
        end_number,
        color=_EPISODE_FILL,
        alpha=0.16,
        label="Episode",
    )


def score_chart(
    points: list[ScorePoint],
    *,
    started_score_ts: datetime,
    ended_score_ts: datetime | None,
    window_end: datetime,
) -> bytes:
    """Reconstruction score against its threshold, with the episode span shaded."""
    if not points:
        raise EmptyChartError("no score points in the chart window")

    times = _as_numbers([point.score_ts for point in points])
    scores = [point.score for point in points]
    threshold = points[-1].threshold
    peak = max(scores)
    peak_at = times[scores.index(peak)]

    figure, axes = plt.subplots(figsize=_FIGURE_SIZE)
    upper = max(peak, threshold) * 1.15
    _ = axes.axhspan(threshold, upper, color=_THRESHOLD_LINE, alpha=0.08)
    _ = axes.axhline(
        threshold,
        color=_THRESHOLD_LINE,
        linestyle="--",
        linewidth=1.2,
        label=f"threshold {threshold:.3e}",
    )
    _mark_episode(axes, started_score_ts, ended_score_ts, window_end)
    _ = axes.plot(
        times, scores, color=_SCORE_LINE, linewidth=1.6, label="Reconstruction error"
    )
    _ = axes.annotate(
        f"peak {peak:.3e}",
        xy=(peak_at, peak),
        xytext=(6, 8),
        textcoords="offset points",
        fontsize=9,
        fontweight="bold",
        color=_THRESHOLD_LINE,
    )
    _ = axes.set_ylabel("Reconstruction error")
    _ = axes.set_ylim(0, upper)
    _time_axis(axes)
    _ = axes.legend(loc="upper left", fontsize=8, framealpha=0.85)
    return _finish(figure)


def telemetry_chart(
    points: list[TelemetryPoint],
    *,
    started_score_ts: datetime,
    ended_score_ts: datetime | None,
    window_end: datetime,
) -> bytes:
    """Temperature and relative humidity over the same window, on paired axes."""
    if not points:
        raise EmptyChartError("no telemetry points in the chart window")

    times = _as_numbers([point.received_ts for point in points])
    temperature = [point.temperature_c for point in points]
    humidity = [point.relative_humidity_pct for point in points]

    figure, axes = plt.subplots(figsize=_FIGURE_SIZE)
    _mark_episode(axes, started_score_ts, ended_score_ts, window_end)
    _ = axes.plot(
        times, temperature, color=_TEMPERATURE_LINE, linewidth=1.6, label="Temperature"
    )
    _ = axes.set_ylabel("Temperature (°C)", color=_TEMPERATURE_LINE)
    axes.tick_params(axis="y", labelcolor=_TEMPERATURE_LINE)
    _time_axis(axes)

    humidity_axes = axes.twinx()
    _ = humidity_axes.plot(
        times, humidity, color=_HUMIDITY_LINE, linewidth=1.6, label="Relative humidity"
    )
    _ = humidity_axes.set_ylabel("Relative humidity (%)", color=_HUMIDITY_LINE)
    humidity_axes.tick_params(axis="y", labelcolor=_HUMIDITY_LINE)
    humidity_axes.spines["top"].set_visible(False)

    score_handles, score_labels = axes.get_legend_handles_labels()
    humidity_handles, humidity_labels = humidity_axes.get_legend_handles_labels()
    _ = axes.legend(
        score_handles + humidity_handles,
        score_labels + humidity_labels,
        loc="upper left",
        fontsize=8,
        framealpha=0.85,
    )
    return _finish(figure)

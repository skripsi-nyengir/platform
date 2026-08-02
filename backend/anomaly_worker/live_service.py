from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Protocol, cast
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from anomaly_backend import tables
from anomaly_backend.sql.live import (
    LIVE_DEVICE_ID,
    BoundaryReason,
    EpisodeCloseReason,
    LiveLeaseLost,
    LiveWindowDesyncError,
    TelemetryKey,
    acquire_writer_lease,
    apply_live_activation,
    commit_boundary_effect,
    insert_live_telemetry,
    live_activation_row,
    live_selection_row,
    mark_telemetry_processed,
    prepare_live_activation,
    processed_live_tail,
    publish_live_inference,
    publish_processing_boundary,
    read_live_cursor,
    release_writer_lease,
    renew_writer_lease,
    resolve_live_episode,
    unprocessed_live_tail,
    write_live_health,
)
from anomaly_worker.live_engine import (
    MAX_GAP,
    Episode,
    EpisodeState,
    WindowEngineState,
    WindowInput,
    check_data_gap,
    close_episode,
    evaluate_score,
    process_input,
)
from anomaly_worker.live_model import (
    IngressModelBinding,
    LiveModelIdentity,
    LiveModelUnavailable,
    load_live_model,
)
from anomaly_worker.scorer import (
    CHANNELS,
    ScoreBatch,
    Scorer,
    ScorerProtocolError,
    TemporalSemantics,
    validate_result,
)


class AcceptedReading(Protocol):
    @property
    def device_id(self) -> str: ...

    @property
    def received_ts(self) -> datetime: ...

    @property
    def received_at_utc(self) -> datetime: ...

    @property
    def temperature_c(self) -> float: ...

    @property
    def relative_humidity_pct(self) -> float: ...


class LiveServiceUnavailable(RuntimeError):
    pass


class LiveScoringModel(Protocol):
    @property
    def identity(self) -> LiveModelIdentity: ...

    @property
    def model_version(self) -> str: ...

    @property
    def threshold(self) -> float: ...

    @property
    def scorer(self) -> Scorer: ...

    @property
    def minimum(self) -> tuple[float, float]: ...

    @property
    def maximum(self) -> tuple[float, float]: ...

    def scale_pair(self, value: tuple[float, float]) -> tuple[float, float]: ...


class LiveModelLoader(Protocol):
    def __call__(
        self,
        connection: AsyncConnection,
        *,
        device_id: str,
        activation_id: int | None = None,
        previous_identity: LiveModelIdentity | None = None,
    ) -> Awaitable[LiveScoringModel]: ...


def _cursor_key(cursor: RowMapping | None) -> TelemetryKey | None:
    if cursor is None or cursor["received_ts"] is None:
        return None
    return cast(datetime, cursor["received_ts"]), cast(UUID, cursor["telemetry_id"])


def _window_input(
    row: RowMapping | Mapping[str, object], identity: LiveModelIdentity
) -> WindowInput:
    return WindowInput(
        received_at_utc=cast(datetime, row["received_at_utc"]),
        model_pair_id=identity.model_pair_id,
        activation_id=identity.activation_id,
        continuity_epoch=cast(int, row["continuity_epoch"]),
        payload=dict(row),
    )


def _continuous_suffix(rows: Sequence[RowMapping]) -> list[RowMapping]:
    if not rows:
        return []
    suffix = [rows[-1]]
    if rows[-1]["segment_start_reason"] is not None:
        return suffix
    for row in reversed(rows[:-1]):
        next_row = suffix[0]
        if (
            cast(datetime, next_row["received_at_utc"])
            - cast(datetime, row["received_at_utc"])
            > MAX_GAP
        ):
            break
        suffix.insert(0, row)
        if row["segment_start_reason"] is not None:
            break
    return suffix


def _scorer_times(window: Sequence[Mapping[str, object]]) -> tuple[datetime, ...]:
    ordered: list[datetime] = []
    for row in window:
        value = (
            cast(datetime, row["received_at_utc"])
            .astimezone(UTC)
            .replace(tzinfo=None)
        )
        if ordered and value <= ordered[-1]:
            value = ordered[-1] + timedelta(microseconds=1)
        ordered.append(value)
    return tuple(ordered)


class LiveService:
    def __init__(
        self,
        engine: AsyncEngine,
        *,
        lease_owner: str,
        model_loader: LiveModelLoader = load_live_model,
        device_id: str = LIVE_DEVICE_ID,
        lease_seconds: int = 30,
        page_size: int = 100,
        alert_actor: str = "live-worker",
    ) -> None:
        if not lease_owner or lease_owner != lease_owner.strip():
            raise ValueError("lease_owner must be a non-empty stable identifier")
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        if page_size < 1:
            raise ValueError("page_size must be positive")
        self._engine = engine
        self._lease_owner = lease_owner
        self._model_loader = model_loader
        self._device_id = device_id
        self._lease_seconds = lease_seconds
        self._page_size = page_size
        self._alert_actor = alert_actor
        self._fencing_token: int | None = None
        self._binding: IngressModelBinding | None = None
        self._segment_reasons: dict[int, BoundaryReason] = {}
        self._window_state = WindowEngineState()
        self._episode_state = EpisodeState()
        self._identities: dict[int, LiveModelIdentity] = {}
        self._models: dict[int, LiveScoringModel] = {}
        self._last_durable_key: TelemetryKey | None = None
        self._last_received_at_utc: datetime | None = None
        self._ingress_lock = asyncio.Lock()
        self._process_lock = asyncio.Lock()
        self._lease_lost = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []
        self._started = False
        self._health_detail_code: str | None = None

    @property
    def binding(self) -> IngressModelBinding:
        if self._binding is None:
            raise LiveServiceUnavailable("live service is not started")
        return self._binding

    @property
    def episode_id(self) -> UUID | None:
        episode = self._episode_state.episode
        return episode.live_episode_id if episode is not None else None

    @property
    def health_detail_code(self) -> str | None:
        return self._health_detail_code

    def _token(self) -> int:
        if self._fencing_token is None or not self._started:
            raise LiveServiceUnavailable("live service is not started")
        if self._lease_lost.is_set():
            raise LiveLeaseLost("live writer lease renewal failed")
        return self._fencing_token

    async def start(self) -> None:
        if self._started:
            return
        async with self._engine.connect() as connection:
            lease = await acquire_writer_lease(
                connection,
                device_id=self._device_id,
                lease_owner=self._lease_owner,
                lease_seconds=self._lease_seconds,
            )
        if lease is None:
            raise LiveServiceUnavailable("another live writer owns the device lease")
        self._fencing_token = cast(int, lease["fencing_token"])
        try:
            async with self._engine.connect() as connection:
                selection = await live_selection_row(
                    connection,
                    device_id=self._device_id,
                )
                if selection is None:
                    raise LiveModelUnavailable("no active live model selection")
                cursor = await read_live_cursor(connection, device_id=self._device_id)
                self._window_state = await self._reconstruct_window(connection, cursor)
                self._episode_state = await self._reconstruct_episode(connection)
                tail = (
                    (
                        await connection.execute(
                            select(tables.live_telemetry)
                            .where(tables.live_telemetry.c.device_id == self._device_id)
                            .order_by(
                                tables.live_telemetry.c.received_ts.desc(),
                                tables.live_telemetry.c.ingress_sequence.desc(),
                            )
                            .limit(1)
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                last_received_at_utc = cast(
                    datetime | None,
                    await connection.scalar(
                        select(func.max(tables.live_telemetry.c.received_at_utc)).where(
                            tables.live_telemetry.c.device_id == self._device_id
                        )
                    ),
                )
                generation = (
                    cast(
                        int,
                        await connection.scalar(
                            select(
                                func.greatest(
                                    func.coalesce(
                                        select(
                                            func.max(
                                                tables.live_telemetry.c.ingress_generation
                                            )
                                        ).scalar_subquery(),
                                        0,
                                    ),
                                    func.coalesce(
                                        select(
                                            func.max(
                                                tables.live_processing_boundaries.c.ingress_generation
                                            )
                                        ).scalar_subquery(),
                                        0,
                                    ),
                                )
                            )
                        ),
                    )
                    + 1
                )
                epoch = (
                    cast(
                        int,
                        await connection.scalar(
                            select(
                                func.greatest(
                                    func.coalesce(
                                        select(
                                            func.max(
                                                tables.live_telemetry.c.continuity_epoch
                                            )
                                        ).scalar_subquery(),
                                        0,
                                    ),
                                    func.coalesce(
                                        select(
                                            func.max(
                                                tables.live_processing_boundaries.c.continuity_epoch
                                            )
                                        ).scalar_subquery(),
                                        0,
                                    ),
                                    func.coalesce(
                                        select(
                                            func.max(
                                                tables.live_cursors.c.continuity_epoch
                                            )
                                        ).scalar_subquery(),
                                        0,
                                    ),
                                )
                            )
                        ),
                    )
                    + 1
                )
                await connection.rollback()

            self._last_durable_key = (
                (
                    cast(datetime, tail["received_ts"]),
                    cast(UUID, tail["telemetry_id"]),
                )
                if tail is not None
                else None
            )
            self._last_received_at_utc = last_received_at_utc
            identity = LiveModelIdentity(
                model_pair_id=cast(UUID, selection["model_pair_id"]),
                activation_id=cast(int, selection["activation_id"]),
                snapshot_corpus_id=cast(str, selection["scaler_snapshot_corpus_id"]),
            )
            self._identities[identity.activation_id] = identity
            self._binding = IngressModelBinding(
                identity=identity,
                ingress_generation=generation,
                continuity_epoch=epoch,
            )
            reason: BoundaryReason = (
                "startup" if tail is None and cursor is None else "lease_takeover"
            )
            async with self._engine.connect() as connection:
                await publish_processing_boundary(
                    connection,
                    device_id=self._device_id,
                    boundary_reason=reason,
                    ingress_generation=generation,
                    continuity_epoch=epoch,
                    fencing_token=cast(int, self._fencing_token),
                    after_key=self._last_durable_key,
                )
            self._segment_reasons[epoch] = reason
            self._started = True
            self._tasks = [
                asyncio.create_task(self._renew_loop()),
                asyncio.create_task(self._watchdog_loop()),
            ]
        except BaseException:
            await self._release_after_failed_start()
            raise

    async def _release_after_failed_start(self) -> None:
        token = self._fencing_token
        if token is not None:
            async with self._engine.connect() as connection:
                await release_writer_lease(
                    connection,
                    device_id=self._device_id,
                    lease_owner=self._lease_owner,
                    fencing_token=token,
                )
        self._fencing_token = None

    async def stop(self, *, release_lease: bool = True) -> None:
        if not self._started:
            return
        self._started = False
        tasks, self._tasks = self._tasks, []
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        token, self._fencing_token = self._fencing_token, None
        if release_lease and token is not None and not self._lease_lost.is_set():
            async with self._engine.connect() as connection:
                await release_writer_lease(
                    connection,
                    device_id=self._device_id,
                    lease_owner=self._lease_owner,
                    fencing_token=token,
                )

    async def _renew_loop(self) -> None:
        interval = max(0.1, self._lease_seconds / 3)
        while True:
            await asyncio.sleep(interval)
            token = self._fencing_token
            if token is None:
                return
            try:
                async with self._engine.connect() as connection:
                    renewed = await renew_writer_lease(
                        connection,
                        device_id=self._device_id,
                        lease_owner=self._lease_owner,
                        fencing_token=token,
                        lease_seconds=self._lease_seconds,
                    )
            except Exception:  # noqa: BLE001 - any renewal failure loses the lease
                self._lease_lost.set()
                return
            if renewed is None:
                self._lease_lost.set()
                return

    async def _watchdog_loop(self) -> None:
        while True:
            await asyncio.sleep(1)
            try:
                await self.watchdog_once()
            except LiveLeaseLost:
                return
            except Exception:  # noqa: BLE001 - watchdog retries transient failures
                self._health_detail_code = "watchdog_retry"

    async def _reconstruct_window(
        self,
        connection: AsyncConnection,
        cursor: RowMapping | None,
    ) -> WindowEngineState:
        key = _cursor_key(cursor)
        if key is None or cursor is None:
            return WindowEngineState()
        cursor_row = (
            (
                await connection.execute(
                    select(tables.live_telemetry).where(
                        tables.live_telemetry.c.device_id == self._device_id,
                        tables.live_telemetry.c.received_ts == key[0],
                        tables.live_telemetry.c.telemetry_id == key[1],
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
        if (
            cursor_row is None
            or cursor_row["processing_status"] != "processed"
            or cursor_row["continuity_epoch"] != cursor["continuity_epoch"]
        ):
            return WindowEngineState()
        activation_id = cast(int, cursor_row["activation_id"])
        activation = await live_activation_row(
            connection,
            device_id=self._device_id,
            activation_id=activation_id,
        )
        if activation is None:
            return WindowEngineState()
        identity = LiveModelIdentity(
            model_pair_id=cast(UUID, activation["model_pair_id"]),
            activation_id=activation_id,
            snapshot_corpus_id=cast(str, activation["scaler_snapshot_corpus_id"]),
        )
        self._identities[activation_id] = identity
        rows = await processed_live_tail(
            connection,
            device_id=self._device_id,
            activation_id=activation_id,
            continuity_epoch=cast(int, cursor["continuity_epoch"]),
            limit=9,
        )
        return WindowEngineState(
            window=tuple(
                _window_input(row, identity) for row in _continuous_suffix(rows)
            )
        )

    async def _reconstruct_episode(
        self,
        connection: AsyncConnection,
    ) -> EpisodeState:
        row = (
            (
                await connection.execute(
                    select(
                        tables.live_alert_episodes,
                        tables.alerts.c.peak_score,
                        tables.alerts.c.threshold,
                    )
                    .join(
                        tables.alerts,
                        tables.alerts.c.alert_id
                        == tables.live_alert_episodes.c.alert_id,
                    )
                    .where(
                        tables.live_alert_episodes.c.device_id == self._device_id,
                        tables.live_alert_episodes.c.status == "open",
                    )
                    .order_by(tables.live_alert_episodes.c.started_score_ts.desc())
                    .limit(1)
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return EpisodeState()
        anomaly_flags = list(
            await connection.scalars(
                select(tables.live_inference.c.is_anomaly)
                .join(
                    tables.live_alert_episode_points,
                    tables.live_alert_episode_points.c.inference_id
                    == tables.live_inference.c.inference_id,
                )
                .where(
                    tables.live_alert_episode_points.c.live_episode_id
                    == row["live_episode_id"]
                )
                .order_by(tables.live_alert_episode_points.c.ordinal.desc())
                .limit(2)
            )
        )
        consecutive_normal = 0
        for is_anomaly in anomaly_flags:
            if is_anomaly:
                break
            consecutive_normal += 1
        severity = (
            "critical"
            if float(row["peak_score"]) / float(row["threshold"]) > 2
            else "warning"
        )
        return EpisodeState(
            Episode(
                live_episode_id=cast(UUID, row["live_episode_id"]),
                status="open",
                severity=severity,
                consecutive_normal=consecutive_normal,
            )
        )

    async def persist_reading(
        self,
        reading: AcceptedReading,
        *,
        telemetry_id: UUID | None = None,
        binding: IngressModelBinding | None = None,
        segment_start_reason: BoundaryReason | None = None,
    ) -> RowMapping:
        if reading.device_id != self._device_id:
            raise ValueError("live reading device does not match service device")
        token = self._token()
        async with self._ingress_lock:
            effective_binding = binding or self.binding
            if (
                binding is None
                and self._last_received_at_utc is not None
                and reading.received_at_utc - self._last_received_at_utc > MAX_GAP
            ):
                effective_binding = IngressModelBinding(
                    identity=self.binding.identity,
                    ingress_generation=self.binding.ingress_generation + 1,
                    continuity_epoch=self.binding.continuity_epoch + 1,
                )
                async with self._engine.connect() as connection:
                    await publish_processing_boundary(
                        connection,
                        device_id=self._device_id,
                        boundary_reason="data_gap",
                        ingress_generation=effective_binding.ingress_generation,
                        continuity_epoch=effective_binding.continuity_epoch,
                        fencing_token=token,
                        after_key=self._last_durable_key,
                    )
                self._binding = effective_binding
                self._segment_reasons[effective_binding.continuity_epoch] = "data_gap"
            reason = segment_start_reason or self._segment_reasons.get(
                effective_binding.continuity_epoch
            )
            key = (reading.received_ts, telemetry_id or uuid4())
            async with self._engine.connect() as connection:
                row = await insert_live_telemetry(
                    connection,
                    telemetry_id=key[1],
                    device_id=self._device_id,
                    received_ts=key[0],
                    received_at_utc=reading.received_at_utc,
                    temperature_c=reading.temperature_c,
                    relative_humidity_pct=reading.relative_humidity_pct,
                    ingress_generation=effective_binding.ingress_generation,
                    activation_id=effective_binding.identity.activation_id,
                    continuity_epoch=effective_binding.continuity_epoch,
                    segment_start_reason=reason,
                    fencing_token=token,
                )
            if reason is not None:
                self._segment_reasons.pop(effective_binding.continuity_epoch, None)
            if self._last_durable_key is None or key > self._last_durable_key:
                self._last_durable_key = key
            if (
                self._last_received_at_utc is None
                or reading.received_at_utc > self._last_received_at_utc
            ):
                self._last_received_at_utc = reading.received_at_utc
            return row

    async def activate(self, *, request_id: UUID, model_pair_id: UUID) -> None:
        token = self._token()
        async with self._ingress_lock:
            current = self.binding
            async with self._engine.connect() as connection:
                async with connection.begin():
                    activation, _ = await prepare_live_activation(
                        connection,
                        request_id=request_id,
                        device_id=self._device_id,
                        model_pair_id=model_pair_id,
                        fencing_token=token,
                    )
                model = await self._model_loader(
                    connection,
                    device_id=self._device_id,
                    activation_id=cast(int, activation["activation_id"]),
                    previous_identity=current.identity,
                )
                await connection.rollback()
                async with connection.begin():
                    await apply_live_activation(
                        connection,
                        request_id=request_id,
                        device_id=self._device_id,
                        model_pair_id=model_pair_id,
                        fencing_token=token,
                        boundary_after_key=self._last_durable_key,
                        boundary_ingress_generation=current.ingress_generation + 1,
                        boundary_continuity_epoch=current.continuity_epoch + 1,
                    )
            self._models[model.identity.activation_id] = model
            self._identities[model.identity.activation_id] = model.identity
            self._binding = IngressModelBinding(
                identity=model.identity,
                ingress_generation=current.ingress_generation + 1,
                continuity_epoch=current.continuity_epoch + 1,
            )
            self._segment_reasons[self.binding.continuity_epoch] = "model_change"

    async def process_pending(self) -> int:
        self._token()
        processed = 0
        async with self._process_lock:
            while True:
                self._token()
                async with self._engine.connect() as connection:
                    cursor = await read_live_cursor(
                        connection,
                        device_id=self._device_id,
                    )
                    items = await unprocessed_live_tail(
                        connection,
                        device_id=self._device_id,
                        after_key=_cursor_key(cursor),
                        last_boundary_id=(
                            cast(int, cursor["last_boundary_id"])
                            if cursor is not None
                            and cursor["last_boundary_id"] is not None
                            else None
                        ),
                        limit=self._page_size,
                    )
                if not items:
                    return processed
                for item in items:
                    if item["kind"] == "boundary":
                        await self._process_boundary(item)
                        continue
                    if not await self._process_telemetry(item):
                        return processed
                    processed += 1
                if len(items) < self._page_size:
                    return processed

    async def _identity_for_activation(self, activation_id: int) -> LiveModelIdentity:
        if identity := self._identities.get(activation_id):
            return identity
        async with self._engine.connect() as connection:
            row = await live_activation_row(
                connection,
                device_id=self._device_id,
                activation_id=activation_id,
            )
        if row is None:
            raise LiveModelUnavailable("persisted live activation is unavailable")
        identity = LiveModelIdentity(
            model_pair_id=cast(UUID, row["model_pair_id"]),
            activation_id=activation_id,
            snapshot_corpus_id=cast(str, row["scaler_snapshot_corpus_id"]),
        )
        self._identities[activation_id] = identity
        return identity

    async def _model_for_activation(self, activation_id: int) -> LiveScoringModel:
        if model := self._models.get(activation_id):
            return model
        async with self._engine.connect() as connection:
            model = await self._model_loader(
                connection,
                device_id=self._device_id,
                activation_id=activation_id,
                previous_identity=None,
            )
        self._models[activation_id] = model
        self._identities[activation_id] = model.identity
        return model

    async def _process_boundary(self, item: Mapping[str, object]) -> None:
        reason = cast(BoundaryReason, item["boundary_reason"])
        transition = close_episode(self._episode_state, reason)
        episode = transition.state.episode if transition.closed else None
        try:
            async with self._engine.connect() as connection:
                await commit_boundary_effect(
                    connection,
                    device_id=self._device_id,
                    boundary_id=cast(int, item["boundary_id"]),
                    fencing_token=self._token(),
                    live_episode_id=(
                        episode.live_episode_id if episode is not None else None
                    ),
                    episode_close_reason=(reason if episode is not None else None),
                    health_status="healthy",
                )
        except Exception:
            self._health_detail_code = "persistence_retry"
            raise
        self._episode_state = transition.state
        self._window_state = WindowEngineState()
        self._health_detail_code = None

    async def _process_telemetry(self, item: Mapping[str, object]) -> bool:
        activation_id = cast(int, item["activation_id"])
        identity = await self._identity_for_activation(activation_id)
        window_transition = process_input(
            self._window_state,
            _window_input(item, identity),
        )
        technical = (
            close_episode(self._episode_state, window_transition.reset_reason)
            if window_transition.reset_reason is not None
            else None
        )
        episode = (
            technical.state.episode
            if technical is not None and technical.closed
            else None
        )
        key = cast(datetime, item["received_ts"]), cast(UUID, item["telemetry_id"])
        if window_transition.window is None:
            try:
                async with self._engine.connect() as connection:
                    changed = await mark_telemetry_processed(
                        connection,
                        device_id=self._device_id,
                        telemetry_key=key,
                        continuity_epoch=cast(int, item["continuity_epoch"]),
                        fencing_token=self._token(),
                        live_episode_id=(
                            episode.live_episode_id if episode is not None else None
                        ),
                        episode_close_reason=(
                            cast(EpisodeCloseReason, window_transition.reset_reason)
                            if episode is not None
                            else None
                        ),
                        health_status="healthy",
                    )
            except Exception:
                self._health_detail_code = "persistence_retry"
                raise
            if changed:
                self._window_state = window_transition.state
                if technical is not None:
                    self._episode_state = technical.state
                self._health_detail_code = None
            return changed

        try:
            model = await self._model_for_activation(activation_id)
            batch = self._score_batch(window_transition.window, model)
            result = await asyncio.to_thread(model.scorer.score, batch)
            validate_result(batch, result, TemporalSemantics.CONTEXT_END)
        except (LiveModelUnavailable, RuntimeError, ScorerProtocolError, ValueError):
            self._health_detail_code = "inference_retry"
            async with self._engine.connect() as connection:
                await write_live_health(
                    connection,
                    device_id=self._device_id,
                    status="degraded",
                    detail_code="inference_retry",
                    fencing_token=self._token(),
                )
            return False

        point = result.points[0]
        score = float(point.score)
        recon = point.reconstruction
        if recon is not None:
            recon_temperature_c: float | None = (
                recon[0] * (model.maximum[0] - model.minimum[0]) + model.minimum[0]
            )
            recon_relative_humidity_pct: float | None = (
                recon[1] * (model.maximum[1] - model.minimum[1]) + model.minimum[1]
            )
        else:
            recon_temperature_c = None
            recon_relative_humidity_pct = None
        next_episode_id = uuid4()
        episode_transition = evaluate_score(
            self._episode_state,
            score=score,
            threshold=model.threshold,
            new_episode_id=next_episode_id,
        )
        next_episode = episode_transition.state.episode
        live_episode_id = (
            next_episode.live_episode_id
            if next_episode is not None
            and (next_episode.status == "open" or episode_transition.closed)
            else None
        )
        is_anomaly = score > model.threshold
        severity = (
            "critical"
            if score / model.threshold > 2
            else "warning"
            if is_anomaly
            else "info"
        )
        source_rows = [
            dict(cast(tuple[tuple[str, object], ...], value.payload))
            for value in window_transition.window
        ]
        source_keys = [
            (cast(datetime, row["received_ts"]), cast(UUID, row["telemetry_id"]))
            for row in source_rows
        ]
        alert_values = (
            self._alert_values(
                live_episode_id=cast(UUID, live_episode_id),
                model=model,
                score=score,
                source_keys=source_keys,
                continuity_epoch=cast(int, item["continuity_epoch"]),
            )
            if episode_transition.opened
            else None
        )
        try:
            async with self._engine.connect() as connection:
                await publish_live_inference(
                    connection,
                    device_id=self._device_id,
                    source_keys=source_keys,
                    score=score,
                    is_anomaly=is_anomaly,
                    severity_at_score=severity,
                    fencing_token=self._token(),
                    live_episode_id=live_episode_id,
                    alert_values=alert_values,
                    alert_actor=(
                        self._alert_actor if alert_values is not None else None
                    ),
                    episode_close_reason=(
                        "normal_recovery" if episode_transition.closed else None
                    ),
                    health_status="healthy",
                    recon_temperature_c=recon_temperature_c,
                    recon_relative_humidity_pct=recon_relative_humidity_pct,
                )
        except LiveWindowDesyncError:
            self._window_state = WindowEngineState()
            self._health_detail_code = "window_desync_reset"
            raise
        except Exception:
            self._health_detail_code = "persistence_retry"
            raise
        self._window_state = window_transition.state
        self._episode_state = episode_transition.state
        self._health_detail_code = None
        return True

    def _score_batch(
        self,
        window: Sequence[WindowInput],
        model: LiveScoringModel,
    ) -> ScoreBatch:
        rows = [
            dict(cast(tuple[tuple[str, object], ...], value.payload))
            for value in window
        ]
        raw_window = tuple(
            (
                float(cast(float, row["temperature_c"])),
                float(cast(float, row["relative_humidity_pct"])),
            )
            for row in rows
        )
        model_window = tuple(model.scale_pair(value) for value in raw_window)
        times = _scorer_times(rows)
        return ScoreBatch(
            model_version=model.model_version,
            schema_version="b02-live-v1",
            channels=CHANNELS,
            raw_values=(raw_window,),
            model_values=(model_window,),
            context_ts=(times,),
            context_start_indices=(0,),
            context_end_indices=(9,),
            segment_ids=(cast(int, rows[-1]["continuity_epoch"]),),
            eligible_window_ordinals=(0,),
            target_ts=(times[-1],),
            window_size=10,
        )

    def _alert_values(
        self,
        *,
        live_episode_id: UUID,
        model: LiveScoringModel,
        score: float,
        source_keys: Sequence[TelemetryKey],
        continuity_epoch: int,
    ) -> dict[str, object]:
        score_ts = source_keys[-1][0]
        return {
            "alert_id": f"live-{live_episode_id.hex}",
            "device_id": self._device_id,
            "detected_at": None,
            "score": score,
            "threshold": model.threshold,
            "model_version": model.model_version,
            "inference_result_window_start_ts": source_keys[0][0],
            "inference_result_window_end_ts": score_ts,
            "detection_basis": "artifact_backed",
            "corpus_id": model.identity.snapshot_corpus_id,
            "episode_start_ts": score_ts,
            "episode_end_ts": score_ts,
            "last_score_ts": score_ts,
            "created_at": datetime.now(UTC),
            "peak_score": score,
            "latest_score": score,
            "anomalous_window_count": 1,
            "replay_job_id": None,
            "segment_id": continuity_epoch,
            "closure_reason": "normal",
            "live_episode_id": live_episode_id,
        }

    async def watchdog_once(self, *, now: datetime | None = None) -> bool:
        self._token()
        async with self._process_lock:
            async with self._ingress_lock:
                episode = self._episode_state.episode
                if episode is None or episode.status == "closed":
                    return False
                last_received = self._last_received_at_utc
                if last_received is None:
                    return False
                async with self._engine.connect() as connection:
                    effective_now = now or cast(
                        datetime,
                        await connection.scalar(select(func.clock_timestamp())),
                    )
                    await connection.rollback()
                    transition = check_data_gap(
                        self._episode_state,
                        last_received_at_utc=last_received,
                        now=effective_now,
                    )
                    if not transition.closed:
                        return False
                    changed = await resolve_live_episode(
                        connection,
                        device_id=self._device_id,
                        live_episode_id=episode.live_episode_id,
                        ended_score_ts=None,
                        fencing_token=self._token(),
                        close_reason="data_gap",
                        health_status="healthy",
                    )
            self._episode_state = transition.state
            self._window_state = WindowEngineState()
            self._health_detail_code = None
            return changed

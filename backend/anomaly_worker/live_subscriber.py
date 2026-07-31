from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import signal
import ssl
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from queue import Full, Queue
from typing import Final, Literal, Protocol, cast
from zoneinfo import ZoneInfo

from paho.mqtt import client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCode
from paho.mqtt.subscribeoptions import SubscribeOptions

from anomaly_backend.config import Settings
from anomaly_backend.db import create_database_engine
from anomaly_backend.sql.live import LIVE_DEVICE_ID

MQTT_CLEAN_START: Final = True
_JAKARTA: Final = ZoneInfo("Asia/Jakarta")
_MAX_RECONNECT_SECONDS: Final = 30
INGRESS_QUEUE_CAPACITY: Final = 100
RuntimeMode = Literal["production", "test"]
_LOGGER = logging.getLogger(__name__)


class MqttConfigurationError(ValueError):
    pass


class MqttMessageRejected(ValueError):
    pass


class MqttProtocolError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class MqttSettings:
    broker_host: str
    broker_port: int
    topic: str
    client_id: str
    tls_enabled: bool
    ca_file: Path | None
    username_file: Path | None = None
    password_file: Path | None = None
    username: str | None = None
    password: str | None = None
    runtime_mode: RuntimeMode = "production"
    reconnect_min_seconds: int = 1
    reconnect_max_seconds: int = _MAX_RECONNECT_SECONDS

    def __post_init__(self) -> None:
        _validate_text(self.broker_host, "MQTT_BROKER_HOST")
        _validate_text(self.topic, "MQTT_TOPIC")
        _validate_text(self.client_id, "MQTT_CLIENT_ID")
        if isinstance(self.broker_port, bool) or not 1 <= self.broker_port <= 65_535:
            raise MqttConfigurationError("MQTT_BROKER_PORT must be a valid port")
        if "+" in self.topic or "#" in self.topic:
            raise MqttConfigurationError("MQTT_TOPIC must be one exact topic")
        if self.runtime_mode not in ("production", "test"):
            raise MqttConfigurationError("LIVE_RUNTIME_MODE is invalid")
        if not isinstance(self.tls_enabled, bool):
            raise MqttConfigurationError("MQTT_TLS_ENABLED must be true or false")
        if not self.tls_enabled and self.runtime_mode != "test":
            raise MqttConfigurationError("TLS may be disabled only in test mode")
        if not self.tls_enabled and self.ca_file is not None:
            raise MqttConfigurationError("MQTT_CA_FILE requires TLS")
        if self.tls_enabled and not _is_file(self.ca_file):
            raise MqttConfigurationError("MQTT_CA_FILE must be a readable file")
        if (self.username_file is None) != (self.password_file is None):
            raise MqttConfigurationError(
                "MQTT username and password files must be configured together"
            )
        if (self.username is None) != (self.password is None):
            raise MqttConfigurationError(
                "MQTT username and password must be configured together"
            )
        if self.username is not None:
            _validate_text(self.username, "MQTT_USERNAME")
            _validate_text(self.password, "MQTT_PASSWORD")
        if self.username is not None and self.username_file is not None:
            raise MqttConfigurationError(
                "MQTT credentials must use environment values or files, not both"
            )
        if self.username_file is not None and not _is_file(self.username_file):
            raise MqttConfigurationError("MQTT credential file is unreadable")
        if self.password_file is not None and not _is_file(self.password_file):
            raise MqttConfigurationError("MQTT credential file is unreadable")
        reconnect_values = (self.reconnect_min_seconds, self.reconnect_max_seconds)
        if any(isinstance(value, bool) or value < 1 for value in reconnect_values):
            raise MqttConfigurationError("MQTT reconnect bounds must be positive")
        if (
            self.reconnect_min_seconds > self.reconnect_max_seconds
            or self.reconnect_max_seconds > _MAX_RECONNECT_SECONDS
        ):
            raise MqttConfigurationError("MQTT reconnect bounds are invalid")

    @classmethod
    def from_environ(cls) -> MqttSettings:
        runtime_mode = os.environ.get("LIVE_RUNTIME_MODE", "production")
        if runtime_mode not in ("production", "test"):
            raise MqttConfigurationError("LIVE_RUNTIME_MODE is invalid")
        return cls(
            broker_host=_required_environment("MQTT_BROKER_HOST"),
            broker_port=_environment_integer("MQTT_BROKER_PORT"),
            topic=_required_environment("MQTT_TOPIC"),
            client_id=_required_environment("MQTT_CLIENT_ID"),
            tls_enabled=_environment_boolean("MQTT_TLS_ENABLED"),
            ca_file=_environment_path("MQTT_CA_FILE"),
            username_file=_environment_path("MQTT_USERNAME_FILE"),
            password_file=_environment_path("MQTT_PASSWORD_FILE"),
            username=_optional_environment("MQTT_USERNAME"),
            password=_optional_environment("MQTT_PASSWORD"),
            runtime_mode=runtime_mode,
            reconnect_min_seconds=_environment_integer(
                "MQTT_RECONNECT_MIN_SECONDS", default="1"
            ),
            reconnect_max_seconds=_environment_integer(
                "MQTT_RECONNECT_MAX_SECONDS", default=str(_MAX_RECONNECT_SECONDS)
            ),
        )


@dataclass(frozen=True, slots=True)
class AcceptedReading:
    device_id: str
    received_ts: datetime
    received_at_utc: datetime
    temperature_c: float
    relative_humidity_pct: float


def _validate_text(value: object, field: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
    ):
        raise MqttConfigurationError(f"{field} is invalid")


def _required_environment(name: str) -> str:
    try:
        value = os.environ[name]
    except KeyError:
        raise MqttConfigurationError(f"{name} is required") from None
    _validate_text(value, name)
    return value


def _environment_integer(name: str, *, default: str | None = None) -> int:
    value = os.environ.get(name, default)
    if value is None or not value.isascii() or not value.isdecimal():
        raise MqttConfigurationError(f"{name} must be an integer")
    return int(value)


def _environment_boolean(name: str) -> bool:
    value = os.environ.get(name)
    if value == "true":
        return True
    if value == "false":
        return False
    raise MqttConfigurationError(f"{name} must be true or false")


def _environment_path(name: str) -> Path | None:
    value = os.environ.get(name)
    if value is None:
        return None
    _validate_text(value, name)
    return Path(value)


def _optional_environment(name: str) -> str | None:
    value = os.environ.get(name)
    if value in (None, ""):
        return None
    _validate_text(value, name)
    return value


def _is_file(path: Path | None) -> bool:
    try:
        return path is not None and path.is_file()
    except OSError:
        return False


def _read_secret(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8").rstrip("\r\n")
    except (OSError, UnicodeError):
        raise MqttConfigurationError("MQTT credential file is unreadable") from None
    if not value or "\x00" in value:
        raise MqttConfigurationError("MQTT credential file is invalid")
    return value


def build_mqtt_client(settings: MqttSettings) -> mqtt.Client:
    client = mqtt.Client(
        callback_api_version=CallbackAPIVersion.VERSION2,
        client_id=settings.client_id,
        protocol=mqtt.MQTTv5,
    )
    client.reconnect_delay_set(
        min_delay=settings.reconnect_min_seconds,
        max_delay=settings.reconnect_max_seconds,
    )
    if settings.tls_enabled:
        client.tls_set(
            ca_certs=str(cast(Path, settings.ca_file)),
            cert_reqs=ssl.CERT_REQUIRED,
            tls_version=ssl.PROTOCOL_TLS_CLIENT,
        )
        client.tls_insecure_set(False)
    if settings.username_file is not None and settings.password_file is not None:
        client.username_pw_set(
            _read_secret(settings.username_file),
            _read_secret(settings.password_file),
        )
    elif settings.username is not None and settings.password is not None:
        client.username_pw_set(settings.username, settings.password)
    return client


def connect_properties() -> Properties:
    properties = Properties(PacketTypes.CONNECT)
    properties.SessionExpiryInterval = 0
    return properties


def subscription_options() -> SubscribeOptions:
    return SubscribeOptions(qos=0, retainAsPublished=True, retainHandling=2)


def validate_suback(
    *, expected_mid: int, mid: int, reason_codes: Sequence[ReasonCode]
) -> None:
    if mid != expected_mid:
        raise MqttProtocolError("SUBACK packet identifier does not match subscription")
    if not reason_codes or any(code.is_failure for code in reason_codes):
        raise MqttProtocolError("MQTT subscription was rejected")


def _reject_constant(_: str) -> object:
    raise MqttMessageRejected("MQTT payload contains a non-finite number")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise MqttMessageRejected("MQTT payload contains a duplicate key")
        result[key] = value
    return result


def parse_payload(payload: bytes) -> tuple[float, float]:
    try:
        parsed = json.loads(
            payload,
            parse_constant=_reject_constant,
            object_pairs_hook=_unique_object,
        )
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError):
        raise MqttMessageRejected("MQTT payload is not valid JSON") from None
    if not isinstance(parsed, dict) or set(parsed) != {"data"}:
        raise MqttMessageRejected("MQTT payload must contain only data")
    values = parsed["data"]
    if not isinstance(values, list) or len(values) != 2:
        raise MqttMessageRejected("MQTT data must contain exactly two values")

    result: list[float] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise MqttMessageRejected("MQTT data values must be numbers")
        try:
            number = float(value)
        except (OverflowError, ValueError):
            raise MqttMessageRejected("MQTT data values must be finite") from None
        if not math.isfinite(number):
            raise MqttMessageRejected("MQTT data values must be finite")
        result.append(number)
    return result[0], result[1]


def handle_message(
    settings: MqttSettings,
    message: mqtt.MQTTMessage,
    *,
    clock: Callable[[], datetime],
    accept: Callable[[AcceptedReading], None],
) -> AcceptedReading:
    if message.topic != settings.topic:
        raise MqttMessageRejected("MQTT message topic does not match")
    if message.retain:
        raise MqttMessageRejected("retained MQTT messages are not accepted")
    temperature_c, relative_humidity_pct = parse_payload(message.payload)

    received = clock()
    if received.tzinfo is None or received.utcoffset() is None:
        raise MqttConfigurationError("clock must return an aware datetime")
    reading = AcceptedReading(
        device_id=LIVE_DEVICE_ID,
        received_ts=received.astimezone(_JAKARTA).replace(
            tzinfo=None, microsecond=0
        ),
        received_at_utc=received.astimezone(UTC),
        temperature_c=temperature_c,
        relative_humidity_pct=relative_humidity_pct,
    )
    accept(reading)
    return reading


class LiveServiceRuntime(Protocol):
    async def start(self) -> None: ...

    async def stop(self, *, release_lease: bool = True) -> None: ...

    async def persist_reading(self, reading: AcceptedReading) -> object: ...

    async def process_pending(self) -> int: ...


class _StopConsumer:
    pass


_STOP_CONSUMER: Final = _StopConsumer()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _report(event: str) -> None:
    _LOGGER.error("%s", event)


async def run_subscriber(
    settings: MqttSettings,
    client: mqtt.Client,
    service: LiveServiceRuntime,
    *,
    stop_event: asyncio.Event,
    report: Callable[[str], None] = _report,
    clock: Callable[[], datetime] = _utc_now,
) -> None:
    ingress: Queue[AcceptedReading | _StopConsumer] = Queue(
        maxsize=INGRESS_QUEUE_CAPACITY
    )
    expected_mid: int | None = None

    def on_connect(
        connected_client: mqtt.Client,
        _userdata: object,
        _flags: mqtt.ConnectFlags,
        reason_code: ReasonCode,
        _properties: Properties | None,
    ) -> None:
        nonlocal expected_mid
        if reason_code.is_failure:
            report("mqtt_connect_rejected")
            return
        result, mid = connected_client.subscribe(
            settings.topic,
            options=subscription_options(),
        )
        if result != mqtt.MQTT_ERR_SUCCESS or mid is None:
            expected_mid = None
            report("mqtt_subscribe_failed")
            return
        expected_mid = mid

    def on_subscribe(
        _client: mqtt.Client,
        _userdata: object,
        mid: int,
        reason_codes: list[ReasonCode],
        _properties: Properties | None,
    ) -> None:
        if expected_mid is None:
            report("mqtt_subscription_unexpected")
            return
        try:
            validate_suback(
                expected_mid=expected_mid,
                mid=mid,
                reason_codes=reason_codes,
            )
        except MqttProtocolError:
            report("mqtt_subscription_rejected")

    def on_disconnect(
        _client: mqtt.Client,
        _userdata: object,
        _flags: mqtt.DisconnectFlags,
        reason_code: ReasonCode,
        _properties: Properties | None,
    ) -> None:
        if reason_code.is_failure:
            report("mqtt_disconnect_qos0_loss_not_recoverable")

    def enqueue(reading: AcceptedReading) -> None:
        ingress.put_nowait(reading)

    def on_message(
        _client: mqtt.Client,
        _userdata: object,
        message: mqtt.MQTTMessage,
    ) -> None:
        try:
            _ = handle_message(settings, message, clock=clock, accept=enqueue)
        except Full:
            report("mqtt_ingress_full_qos0_loss_not_recoverable")
        except MqttMessageRejected:
            report("mqtt_message_rejected")

    async def consume() -> None:
        while True:
            item = await asyncio.to_thread(ingress.get)
            try:
                if isinstance(item, _StopConsumer):
                    return
                try:
                    _ = await service.persist_reading(item)
                except Exception:  # noqa: BLE001 - isolate one QoS 0 reading
                    report("live_persistence_failed_qos0_loss_not_recoverable")
                    continue
                try:
                    _ = await service.process_pending()
                except Exception:  # noqa: BLE001 - leave durable work for retry
                    report("live_processing_deferred")
            finally:
                ingress.task_done()

    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    await service.start()
    try:
        try:
            _ = await service.process_pending()
        except Exception:  # noqa: BLE001 - startup retries durable pending work
            report("live_processing_deferred")
        consumer = asyncio.create_task(consume())
        loop_started = False
        try:
            result = client.connect(
                settings.broker_host,
                settings.broker_port,
                keepalive=60,
                clean_start=MQTT_CLEAN_START,
                properties=connect_properties(),
            )
            if result != mqtt.MQTT_ERR_SUCCESS:
                raise MqttProtocolError("MQTT connection could not be started")
            result = client.loop_start()
            if result != mqtt.MQTT_ERR_SUCCESS:
                raise MqttProtocolError("MQTT network loop could not be started")
            loop_started = True
            _ = await stop_event.wait()
        finally:
            client.on_message = None
            await asyncio.to_thread(ingress.put, _STOP_CONSUMER)
            await consumer
            if loop_started:
                _ = client.disconnect()
                _ = client.loop_stop()
    finally:
        await service.stop()


async def _main() -> None:
    settings = MqttSettings.from_environ()
    database_settings = Settings.from_environ()
    engine = create_database_engine(database_settings)
    client = build_mqtt_client(settings)

    from anomaly_worker.live_service import LiveService

    service = LiveService(engine, lease_owner=settings.client_id)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for shutdown_signal in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(shutdown_signal, stop_event.set)
    try:
        await run_subscriber(
            settings,
            client,
            service,
            stop_event=stop_event,
        )
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()

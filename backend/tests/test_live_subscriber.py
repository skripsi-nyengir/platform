from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import ssl
import sys
from typing import ClassVar, cast, final
from unittest.mock import patch
from uuid import uuid4

from paho.mqtt import client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCode
from paho.mqtt.subscribeoptions import SubscribeOptions
import pytest

from anomaly_backend.sql.live import LIVE_DEVICE_ID
from anomaly_worker.live_subscriber import (
    INGRESS_QUEUE_CAPACITY,
    MQTT_CLEAN_START,
    AcceptedReading,
    MqttConfigurationError,
    MqttMessageRejected,
    MqttProtocolError,
    MqttSettings,
    build_mqtt_client,
    connect_properties,
    handle_message,
    main,
    parse_payload,
    run_subscriber,
    subscription_options,
    validate_suback,
)


def _test_environment() -> dict[str, str]:
    return {
        "MQTT_BROKER_HOST": "broker",
        "MQTT_BROKER_PORT": "1883",
        "MQTT_TOPIC": "telemetry/b02f3872",
        "MQTT_CLIENT_ID": "live-b02f3872",
        "MQTT_TLS_ENABLED": "false",
        "LIVE_RUNTIME_MODE": "test",
    }


def _settings(environment: dict[str, str] | None = None) -> MqttSettings:
    with patch.dict(os.environ, environment or _test_environment(), clear=True):
        return MqttSettings.from_environ()


def _message(
    *,
    topic: str = "telemetry/b02f3872",
    payload: bytes = b'{"data":[23.5,61]}',
    retained: bool = False,
) -> mqtt.MQTTMessage:
    message = mqtt.MQTTMessage()
    message.topic = topic.encode()
    message.payload = payload
    message.retain = retained
    return message


def test_parse_payload_accepts_only_the_exact_finite_pair() -> None:
    assert parse_payload(b'{"data":[23.5,61]}') == (23.5, 61.0)


def test_parse_payload_rejects_deep_nesting_without_leaking_recursion_error() -> None:
    depth = sys.getrecursionlimit() * 10
    payload = b"[" * depth + b"0" + b"]" * depth

    with pytest.raises(MqttMessageRejected):
        parse_payload(payload)


@pytest.mark.parametrize(
    "payload",
    [
        b"{}",
        b'{"other":[23.5,61]}',
        b'{"data":[23.5,61],"extra":true}',
        b'{"data":[23.5]}',
        b'{"data":[23.5,61,70]}',
        b'{"data":["23.5",61]}',
        b'{"data":[true,61]}',
        b'{"data":[23.5,false]}',
        b'{"data":[NaN,61]}',
        b'{"data":[Infinity,61]}',
        b'{"data":[-Infinity,61]}',
        b'{"data":[1e999,61]}',
        b'{"data":[23.5,61]',
        b'[{"data":[23.5,61]}]',
        b"null",
        b'{"data":[23.5,61],"data":[23.5,61]}',
    ],
)
def test_parse_payload_rejects_every_other_shape(payload: bytes) -> None:
    with pytest.raises(MqttMessageRejected):
        parse_payload(payload)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("MQTT_BROKER_HOST", ""),
        ("MQTT_BROKER_HOST", " broker"),
        ("MQTT_BROKER_PORT", "0"),
        ("MQTT_BROKER_PORT", "65536"),
        ("MQTT_BROKER_PORT", "1883.0"),
        ("MQTT_TOPIC", ""),
        ("MQTT_TOPIC", "telemetry/+"),
        ("MQTT_TOPIC", "telemetry/#"),
        ("MQTT_CLIENT_ID", ""),
        ("MQTT_TLS_ENABLED", "yes"),
        ("LIVE_RUNTIME_MODE", "staging"),
        ("MQTT_RECONNECT_MIN_SECONDS", "0"),
        ("MQTT_RECONNECT_MAX_SECONDS", "0"),
        ("MQTT_RECONNECT_MAX_SECONDS", "31"),
    ],
)
def test_settings_reject_invalid_environment_values(key: str, value: str) -> None:
    environment = _test_environment()
    environment[key] = value

    with patch.dict(os.environ, environment, clear=True):
        with pytest.raises(MqttConfigurationError):
            MqttSettings.from_environ()


@pytest.mark.parametrize(
    "missing",
    [
        "MQTT_BROKER_HOST",
        "MQTT_BROKER_PORT",
        "MQTT_TOPIC",
        "MQTT_CLIENT_ID",
        "MQTT_TLS_ENABLED",
    ],
)
def test_settings_require_every_mqtt_variable(missing: str) -> None:
    environment = _test_environment()
    del environment[missing]

    with patch.dict(os.environ, environment, clear=True):
        with pytest.raises(MqttConfigurationError):
            MqttSettings.from_environ()


def test_settings_default_to_production_and_reject_tls_off() -> None:
    environment = _test_environment()
    del environment["LIVE_RUNTIME_MODE"]

    with patch.dict(os.environ, environment, clear=True):
        with pytest.raises(MqttConfigurationError):
            MqttSettings.from_environ()


def test_settings_allow_tls_off_only_in_test_mode() -> None:
    settings = _settings()

    assert settings.runtime_mode == "test"
    assert settings.tls_enabled is False
    assert settings.reconnect_min_seconds == 1
    assert settings.reconnect_max_seconds == 30


@pytest.mark.parametrize(
    ("present", "missing"),
    [
        ("MQTT_USERNAME_FILE", "MQTT_PASSWORD_FILE"),
        ("MQTT_PASSWORD_FILE", "MQTT_USERNAME_FILE"),
    ],
)
def test_settings_reject_one_sided_credentials(
    tmp_path: Path, present: str, missing: str
) -> None:
    credential_file = tmp_path / "credential"
    credential_file.write_text(uuid4().hex)
    environment = _test_environment()
    environment[present] = str(credential_file)
    environment.pop(missing, None)

    with patch.dict(os.environ, environment, clear=True):
        with pytest.raises(MqttConfigurationError):
            MqttSettings.from_environ()


def test_settings_require_a_readable_ca_file_when_tls_is_enabled(
    tmp_path: Path,
) -> None:
    environment = _test_environment()
    environment.update(
        {
            "LIVE_RUNTIME_MODE": "production",
            "MQTT_TLS_ENABLED": "true",
            "MQTT_CA_FILE": str(tmp_path / "missing-ca.pem"),
        }
    )

    with patch.dict(os.environ, environment, clear=True):
        with pytest.raises(MqttConfigurationError):
            MqttSettings.from_environ()


def test_settings_reject_a_ca_file_when_tls_is_disabled(tmp_path: Path) -> None:
    ca_file = tmp_path / "ca.pem"
    ca_file.write_text("certificate-placeholder")
    environment = _test_environment()
    environment["MQTT_CA_FILE"] = str(ca_file)

    with patch.dict(os.environ, environment, clear=True):
        with pytest.raises(MqttConfigurationError):
            MqttSettings.from_environ()


@final
class _FakeClient:
    instances: ClassVar[list[_FakeClient]] = []

    def __init__(self, *, events: list[str] | None = None, **arguments: object) -> None:
        self.arguments = arguments
        self.events = events
        self.reconnect_delays: tuple[int, int] | None = None
        self.tls_arguments: dict[str, object] | None = None
        self.tls_insecure: bool | None = None
        self.credentials_configured = False
        self.credentials: tuple[str, str] | None = None
        self.on_connect: Callable[..., None] | None = None
        self.on_disconnect: Callable[..., None] | None = None
        self.on_message: Callable[..., None] | None = None
        self.on_subscribe: Callable[..., None] | None = None
        self.connect_calls: list[dict[str, object]] = []
        self.subscriptions: list[tuple[str, SubscribeOptions]] = []
        self.loop_started = False
        self.loop_stopped = False
        self.disconnected = False
        self._next_mid = 1
        self.instances.append(self)

    def reconnect_delay_set(self, *, min_delay: int, max_delay: int) -> None:
        self.reconnect_delays = (min_delay, max_delay)

    def tls_set(self, **arguments: object) -> None:
        self.tls_arguments = arguments

    def tls_insecure_set(self, value: bool) -> None:
        self.tls_insecure = value

    def username_pw_set(self, username: str, password: str | None = None) -> None:
        assert username
        assert password
        self.credentials_configured = True
        self.credentials = (username, password)

    def connect(
        self,
        host: str,
        port: int,
        keepalive: int,
        *,
        clean_start: bool,
        properties: Properties,
    ) -> int:
        self.connect_calls.append(
            {
                "host": host,
                "port": port,
                "keepalive": keepalive,
                "clean_start": clean_start,
                "properties": properties,
            }
        )
        return mqtt.MQTT_ERR_SUCCESS

    def loop_start(self) -> int:
        self.loop_started = True
        return mqtt.MQTT_ERR_SUCCESS

    def loop_stop(self) -> int:
        self.loop_stopped = True
        return mqtt.MQTT_ERR_SUCCESS

    def disconnect(self) -> int:
        self.disconnected = True
        if self.events is not None:
            self.events.append("disconnect")
        return mqtt.MQTT_ERR_SUCCESS

    def subscribe(
        self,
        topic: str,
        *,
        options: SubscribeOptions,
    ) -> tuple[int, int]:
        mid = self._next_mid
        self._next_mid += 1
        self.subscriptions.append((topic, options))
        return mqtt.MQTT_ERR_SUCCESS, mid

    def fire_connect(self) -> None:
        callback = cast(Callable[..., None], self.on_connect)
        callback(
            self,
            None,
            mqtt.ConnectFlags(session_present=False),
            ReasonCode(PacketTypes.CONNACK, "Success"),
            None,
        )

    def fire_subscribe(self) -> None:
        callback = cast(Callable[..., None], self.on_subscribe)
        callback(
            self,
            None,
            self._next_mid - 1,
            [ReasonCode(PacketTypes.SUBACK, "Granted QoS 0")],
            None,
        )

    def fire_disconnect(self) -> None:
        callback = cast(Callable[..., None], self.on_disconnect)
        callback(
            self,
            None,
            mqtt.DisconnectFlags(is_disconnect_packet_from_server=False),
            ReasonCode(PacketTypes.DISCONNECT, "Unspecified error"),
            None,
        )

    def fire_message(self, message: mqtt.MQTTMessage | None = None) -> None:
        callback = cast(Callable[..., None], self.on_message)
        callback(self, None, message or _message())


@final
class _FakeLiveService:
    def __init__(
        self,
        *,
        persistence_error: Exception | None = None,
        persistence_release: asyncio.Event | None = None,
        events: list[str] | None = None,
    ) -> None:
        self.persistence_error = persistence_error
        self.persistence_release = persistence_release
        self.events = events
        self.readings: list[AcceptedReading] = []
        self.started = False
        self.stopped = False
        self.process_calls = 0
        self.persistence_attempted = asyncio.Event()

    async def start(self) -> None:
        self.started = True

    async def stop(self, *, release_lease: bool = True) -> None:
        assert release_lease
        self.stopped = True

    async def persist_reading(self, reading: AcceptedReading) -> object:
        self.persistence_attempted.set()
        if self.persistence_release is not None:
            await self.persistence_release.wait()
        if self.persistence_error is not None:
            raise self.persistence_error
        self.readings.append(reading)
        if self.events is not None:
            self.events.append("persisted")
        return object()

    async def process_pending(self) -> int:
        self.process_calls += 1
        return len(self.readings)


def test_mqtt_client_uses_v2_mqtt5_verified_tls_and_secret_files(
    tmp_path: Path,
) -> None:
    ca_file = tmp_path / "ca.pem"
    username_file = tmp_path / "username"
    password_file = tmp_path / "password"
    ca_file.write_text("certificate-placeholder")
    username_file.write_text(uuid4().hex)
    password_file.write_text(uuid4().hex)
    environment = _test_environment()
    environment.update(
        {
            "LIVE_RUNTIME_MODE": "production",
            "MQTT_TLS_ENABLED": "true",
            "MQTT_CA_FILE": str(ca_file),
            "MQTT_USERNAME_FILE": str(username_file),
            "MQTT_PASSWORD_FILE": str(password_file),
            "MQTT_RECONNECT_MIN_SECONDS": "2",
            "MQTT_RECONNECT_MAX_SECONDS": "20",
        }
    )
    settings = _settings(environment)

    _FakeClient.instances.clear()
    with patch("anomaly_worker.live_subscriber.mqtt.Client", _FakeClient):
        _ = build_mqtt_client(settings)
    client = _FakeClient.instances[-1]

    assert client.arguments == {
        "callback_api_version": CallbackAPIVersion.VERSION2,
        "client_id": "live-b02f3872",
        "protocol": mqtt.MQTTv5,
    }
    assert client.reconnect_delays == (2, 20)
    assert client.tls_arguments == {
        "ca_certs": str(ca_file),
        "cert_reqs": ssl.CERT_REQUIRED,
        "tls_version": ssl.PROTOCOL_TLS_CLIENT,
    }
    assert client.tls_insecure is False
    assert client.credentials_configured is True


def test_mqtt_client_accepts_only_paired_environment_credentials() -> None:
    environment = _test_environment() | {
        "MQTT_USERNAME": "subscriber",
        "MQTT_PASSWORD": "secret-placeholder",
    }
    settings = _settings(environment)

    _FakeClient.instances.clear()
    with patch("anomaly_worker.live_subscriber.mqtt.Client", _FakeClient):
        _ = build_mqtt_client(settings)
    assert _FakeClient.instances[-1].credentials == (
        "subscriber",
        "secret-placeholder",
    )

    del environment["MQTT_PASSWORD"]
    with patch.dict(os.environ, environment, clear=True):
        with pytest.raises(MqttConfigurationError, match="configured together"):
            MqttSettings.from_environ()


def test_mqtt5_connection_and_subscription_options_are_explicit() -> None:
    properties = connect_properties()
    options = subscription_options()

    assert MQTT_CLEAN_START is True
    assert properties.packetType == PacketTypes.CONNECT
    assert getattr(properties, "SessionExpiryInterval") == 0
    assert options.QoS == 0
    assert options.retainHandling == 2
    assert options.retainAsPublished is True


def test_suback_requires_the_matching_packet_id_and_all_success_codes() -> None:
    validate_suback(
        expected_mid=17,
        mid=17,
        reason_codes=[ReasonCode(PacketTypes.SUBACK, "Granted QoS 0")],
    )

    with pytest.raises(MqttProtocolError):
        validate_suback(
            expected_mid=17,
            mid=18,
            reason_codes=[ReasonCode(PacketTypes.SUBACK, "Granted QoS 0")],
        )
    with pytest.raises(MqttProtocolError):
        validate_suback(expected_mid=17, mid=17, reason_codes=[])
    with pytest.raises(MqttProtocolError):
        validate_suback(
            expected_mid=17,
            mid=17,
            reason_codes=[
                ReasonCode(PacketTypes.SUBACK, "Granted QoS 0"),
                ReasonCode(PacketTypes.SUBACK, "Unspecified error"),
            ],
        )


def test_valid_message_uses_one_aware_clock_read_and_jakarta_naive_seconds() -> None:
    settings = _settings()
    calls = 0
    instant = datetime(
        2026,
        7,
        31,
        8,
        9,
        10,
        987654,
        tzinfo=timezone(timedelta(hours=2)),
    )
    accepted: list[AcceptedReading] = []

    def clock() -> datetime:
        nonlocal calls
        calls += 1
        return instant

    reading = handle_message(
        settings,
        _message(),
        clock=clock,
        accept=accepted.append,
    )

    assert calls == 1
    assert accepted == [reading]
    assert reading.device_id == LIVE_DEVICE_ID
    assert reading.temperature_c == 23.5
    assert reading.relative_humidity_pct == 61.0
    assert reading.received_at_utc == datetime(
        2026, 7, 31, 6, 9, 10, 987654, tzinfo=timezone.utc
    )
    assert reading.received_ts == datetime(2026, 7, 31, 13, 9, 10)
    assert reading.received_ts.tzinfo is None


@pytest.mark.parametrize(
    "message",
    [
        _message(topic="telemetry/other"),
        _message(retained=True),
        _message(payload=b'{"data":[true,61]}'),
    ],
)
def test_rejected_messages_never_read_the_clock_or_reach_the_acceptor(
    message: mqtt.MQTTMessage,
) -> None:
    def unexpected_clock() -> datetime:
        raise AssertionError("rejected message read the clock")

    def unexpected_accept(_: AcceptedReading) -> None:
        raise AssertionError("rejected message reached the acceptor")

    with pytest.raises(MqttMessageRejected):
        handle_message(
            _settings(),
            message,
            clock=unexpected_clock,
            accept=unexpected_accept,
        )


def test_clock_must_return_an_aware_datetime() -> None:
    with pytest.raises(MqttConfigurationError):
        handle_message(
            _settings(),
            _message(),
            clock=lambda: datetime(2026, 7, 31),
            accept=lambda _: None,
        )


async def _start_runtime(
    client: _FakeClient,
    service: _FakeLiveService,
    stop_event: asyncio.Event,
    reports: list[str],
) -> asyncio.Task[None]:
    task = asyncio.create_task(
        run_subscriber(
            _settings(),
            cast(mqtt.Client, cast(object, client)),
            service,
            stop_event=stop_event,
            report=reports.append,
        )
    )
    for _ in range(100):
        if client.connect_calls:
            return task
        await asyncio.sleep(0)
    raise AssertionError("subscriber did not connect")


def test_runtime_subscribes_qos_zero_routes_to_service_and_shuts_down() -> None:
    async def run() -> None:
        client = _FakeClient()
        service = _FakeLiveService()
        stop_event = asyncio.Event()
        reports: list[str] = []
        task = await _start_runtime(client, service, stop_event, reports)

        client.fire_connect()
        assert len(client.subscriptions) == 1
        topic, options = client.subscriptions[0]
        assert topic == "telemetry/b02f3872"
        assert options.QoS == 0
        client.fire_subscribe()
        client.fire_message()
        await asyncio.wait_for(service.persistence_attempted.wait(), timeout=1)

        stop_event.set()
        await asyncio.wait_for(task, timeout=1)
        assert service.started
        assert len(service.readings) == 1
        assert service.process_calls == 2
        assert service.stopped
        assert client.disconnected
        assert client.loop_stopped
        assert reports == []

    asyncio.run(run())


def test_shutdown_drains_accepted_reading_before_mqtt_disconnect() -> None:
    async def run() -> None:
        events: list[str] = []
        persistence_release = asyncio.Event()
        client = _FakeClient(events=events)
        service = _FakeLiveService(
            persistence_release=persistence_release,
            events=events,
        )
        stop_event = asyncio.Event()
        reports: list[str] = []
        task = await _start_runtime(client, service, stop_event, reports)

        client.fire_message()
        await asyncio.wait_for(service.persistence_attempted.wait(), timeout=1)
        stop_event.set()
        try:
            await asyncio.sleep(0)
            assert not client.disconnected
        finally:
            persistence_release.set()
            await asyncio.wait_for(task, timeout=1)

        assert events == ["persisted", "disconnect"]
        assert reports == []

    asyncio.run(run())


def test_bounded_ingress_queue_reports_newest_qos_zero_loss() -> None:
    async def run() -> None:
        persistence_release = asyncio.Event()
        client = _FakeClient()
        service = _FakeLiveService(persistence_release=persistence_release)
        stop_event = asyncio.Event()
        reports: list[str] = []
        task = await _start_runtime(client, service, stop_event, reports)

        client.fire_message()
        await asyncio.wait_for(service.persistence_attempted.wait(), timeout=1)
        for _ in range(INGRESS_QUEUE_CAPACITY + 1):
            client.fire_message()

        assert reports == ["mqtt_ingress_full_qos0_loss_not_recoverable"]
        persistence_release.set()
        stop_event.set()
        await asyncio.wait_for(task, timeout=1)

    asyncio.run(run())


def test_disconnect_resubscribes_without_recovering_qos_zero_loss() -> None:
    async def run() -> None:
        client = _FakeClient()
        service = _FakeLiveService()
        stop_event = asyncio.Event()
        reports: list[str] = []
        task = await _start_runtime(client, service, stop_event, reports)

        client.fire_connect()
        client.fire_subscribe()
        client.fire_disconnect()
        client.fire_connect()
        client.fire_subscribe()
        client.fire_message(_message(payload=b'{"data":[24,62]}'))
        await asyncio.wait_for(service.persistence_attempted.wait(), timeout=1)

        stop_event.set()
        await asyncio.wait_for(task, timeout=1)
        assert len(client.subscriptions) == 2
        assert len(service.readings) == 1
        assert service.readings[0].temperature_c == 24
        assert reports == ["mqtt_disconnect_qos0_loss_not_recoverable"]

    asyncio.run(run())


def test_persistence_failure_is_reported_without_retry_or_spool() -> None:
    async def run() -> None:
        client = _FakeClient()
        service = _FakeLiveService(persistence_error=RuntimeError("database unavailable"))
        stop_event = asyncio.Event()
        reports: list[str] = []
        task = await _start_runtime(client, service, stop_event, reports)

        client.fire_connect()
        client.fire_subscribe()
        client.fire_message()
        await asyncio.wait_for(service.persistence_attempted.wait(), timeout=1)
        for _ in range(100):
            if reports:
                break
            await asyncio.sleep(0)

        stop_event.set()
        await asyncio.wait_for(task, timeout=1)
        assert service.readings == []
        assert service.process_calls == 1
        assert reports == ["live_persistence_failed_qos0_loss_not_recoverable"]

    asyncio.run(run())


def test_main_validates_mqtt_settings_before_creating_network_client() -> None:
    with (
        patch.dict(os.environ, {}, clear=True),
        patch("anomaly_worker.live_subscriber.build_mqtt_client") as build_client,
        patch("anomaly_worker.live_subscriber.create_database_engine") as create_engine,
        pytest.raises(MqttConfigurationError),
    ):
        main()

    build_client.assert_not_called()
    create_engine.assert_not_called()

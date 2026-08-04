from pathlib import Path


def test_production_compose_uses_only_immutable_published_images() -> None:
    root = Path(__file__).parents[2]
    compose = (root / "compose.production.cpu.yaml").read_text(encoding="utf-8")

    assert compose.count("build: !reset null") == 7
    assert compose.count("${RUNTIME_IMAGE:?") == 3
    assert compose.count("${WORKER_IMAGE:?") == 3
    assert compose.count("${WEB_IMAGE:?") == 1
    assert "LIVE_RUNTIME_MODE: production" in compose
    assert 'MQTT_TLS_ENABLED: "true"' in compose
    assert "MQTT_CA_FILE: /run/secrets/mqtt-ca.crt" in compose
    assert "/opt/anomaly-platform/shared/mqtt-ca.crt:/run/secrets/mqtt-ca.crt:ro" in compose
    for service in ("eda-worker", "eda-cli", "import", "eda-import", "sim-import"):
        assert f"  {service}: !reset null" in compose

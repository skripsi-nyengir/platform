# Web Dashboard & Live Inference — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a web dashboard with live inference pipeline for IoT anomaly detection — Laravel+React dashboard, Python MQTT consumer, Python ONNX inference service, and Docker Compose infrastructure.

**Architecture:** Split-consumer pattern — Consumer service subscribes to MQTT, fans out to Redis (real-time) and ClickHouse (historical). Inference service polls Redis, runs ONNX model, writes alerts to MySQL. Laravel dashboard polls Redis for sensor display and queries MySQL for alerts.

**Tech Stack:** Laravel 12 + React (Breeze), Python 3.12, paho-mqtt, onnxruntime, FastAPI, Redis 7, ClickHouse, MySQL 8, EMQX 5, Docker Compose

## Global Constraints

- Python 3.12 for all Python services
- Laravel 12 with Breeze + React + Inertia.js
- All services on `bpom-net` Docker bridge network
- MQTT topic pattern: `/bpom/sensor/{device_id}` with JSON payload `{"ts", "suhu", "rh"}`
- Redis key pattern: `sensor:{device_id}:latest` with TTL 300s
- Window size = 30 timesteps, inference interval = 60s
- No hardcoded passwords — use environment variables
- Indonesian + English technical terms (mixed) in UI and docs

---

### Task 1: Docker Infrastructure Setup

**Files:**
- Create: `docker-compose.yml`
- Create: `infra/clickhouse/init.sql`
- Create: `.env.example`

**Interfaces:**
- Produces: Running EMQX (`:1883`, `:18083`), Redis (`:6379`), ClickHouse (`:8123`, `:9000`), MySQL (`:3306`)
- Consumed by: All subsequent tasks

- [ ] **Step 1: Create `.env.example`**

```bash
# .env.example
# MQTT
MQTT_BROKER=localhost
MQTT_PORT=1883

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# ClickHouse
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=9000
CLICKHOUSE_DB=bpom_sensors
CLICKHOUSE_USER=bpom
CLICKHOUSE_PASSWORD=bpom_secret

# MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_ROOT_PASSWORD=root_secret
MYSQL_DATABASE=bpom_web
MYSQL_USER=bpom
MYSQL_PASSWORD=bpom_secret

# Inference
MODEL_PATH=./models/best_model.onnx
CONFIG_PATH=./configs/thresholds.yaml
INFERENCE_INTERVAL=60
WINDOW_SIZE=30
```

- [ ] **Step 2: Create ClickHouse init SQL**

```sql
-- infra/clickhouse/init.sql
CREATE DATABASE IF NOT EXISTS bpom_sensors;

CREATE TABLE IF NOT EXISTS bpom_sensors.sensor_data
(
    device_id   LowCardinality(String),
    timestamp   DateTime64(3, 'Asia/Jakarta'),
    suhu        Float64,
    rh          Float64
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (device_id, timestamp)
TTL timestamp + INTERVAL 90 DAY;
```

- [ ] **Step 3: Create `docker-compose.yml`**

```yaml
version: "3.8"

services:
  emqx:
    image: emqx/emqx:5.8
    container_name: bpom-emqx
    ports:
      - "1883:1883"
      - "8083:8083"
      - "18083:18083"
    environment:
      EMQX_NAME: bpom-mqtt
      EMQX_HOST: 127.0.0.1
    volumes:
      - emqx_data:/opt/emqx/data
      - emqx_log:/opt/emqx/log
    restart: unless-stopped
    networks:
      - bpom-net

  redis:
    image: redis:7-alpine
    container_name: bpom-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
    networks:
      - bpom-net

  clickhouse:
    image: clickhouse/clickhouse-server:24.3
    container_name: bpom-clickhouse
    ports:
      - "8123:8123"
      - "9000:9000"
    environment:
      CLICKHOUSE_DB: bpom_sensors
      CLICKHOUSE_USER: bpom
      CLICKHOUSE_PASSWORD: bpom_secret
    volumes:
      - clickhouse_data:/var/lib/clickhouse
      - ./infra/clickhouse/init.sql:/docker-entrypoint-initdb.d/init.sql
    restart: unless-stopped
    networks:
      - bpom-net

  mysql:
    image: mysql:8.0
    container_name: bpom-mysql
    ports:
      - "3306:3306"
    environment:
      MYSQL_ROOT_PASSWORD: root_secret
      MYSQL_DATABASE: bpom_web
      MYSQL_USER: bpom
      MYSQL_PASSWORD: bpom_secret
    volumes:
      - mysql_data:/var/lib/mysql
    restart: unless-stopped
    networks:
      - bpom-net

networks:
  bpom-net:
    driver: bridge

volumes:
  emqx_data:
  emqx_log:
  redis_data:
  clickhouse_data:
  mysql_data:
```

- [ ] **Step 4: Start infrastructure and verify**

```bash
cd /media/dandy/College/SEMESTER_VIII/anomaly-detection
cp .env.example .env
docker-compose up -d
```

Verify all services running:

```bash
docker-compose ps
# All 4 services should show "Up"

# Test EMQX
curl -s http://localhost:18083/api/v5/status
# Should return JSON with "node_status":"running"

# Test Redis
redis-cli ping
# Should return PONG

# Test ClickHouse
curl -s http://localhost:8123/ping
# Should return Ok.

# Test MySQL
mysql -h 127.0.0.1 -u bpom -pbpom_secret -e "SELECT 1"
# Should return 1
```

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml .env.example infra/ .env
git commit -m "feat: docker infrastructure - emqx, redis, clickhouse, mysql"
```

---

### Task 2: Consumer Service — MQTT → Redis + ClickHouse

**Files:**
- Create: `services/consumer/main.py`
- Create: `services/consumer/requirements.txt`
- Create: `services/consumer/Dockerfile`

**Interfaces:**
- Consumes: MQTT messages on `/bpom/sensor/+` (JSON: `{"ts", "suhu", "rh"}`)
- Produces: Redis keys `sensor:{id}:latest` (JSON, TTL 300s), ClickHouse `bpom_sensors.sensor_data` rows

- [ ] **Step 1: Create requirements.txt**

```
# services/consumer/requirements.txt
paho-mqtt==1.6.1
redis==5.0.0
clickhouse-driver==0.2.7
```

- [ ] **Step 2: Create `main.py`**

```python
# services/consumer/main.py
"""
MQTT Consumer — subscribes to all sensor topics,
writes to Redis (latest) and ClickHouse (historical).
"""
import json
import logging
import os
import time

import paho.mqtt.client as mqtt
import redis
from clickhouse_driver import Client as CHClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MQTT_BROKER = os.environ.get("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", "/bpom/sensor/+")

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))

CLICKHOUSE_HOST = os.environ.get("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.environ.get("CLICKHOUSE_PORT", 9000))
CLICKHOUSE_DB = os.environ.get("CLICKHOUSE_DB", "bpom_sensors")
CLICKHOUSE_USER = os.environ.get("CLICKHOUSE_USER", "bpom")
CLICKHOUSE_PASSWORD = os.environ.get("CLICKHOUSE_PASSWORD", "bpom_secret")

BATCH_SIZE = int(os.environ.get("BATCH_SIZE", 100))
FLUSH_INTERVAL = int(os.environ.get("FLUSH_INTERVAL", 5))
REDIS_TTL = int(os.environ.get("REDIS_TTL", 300))


class Consumer:
    def __init__(self):
        self.redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        self.ch = CHClient(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_PORT,
            database=CLICKHOUSE_DB,
            user=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD,
        )
        self.buffer: list[tuple] = []
        self.last_flush = time.time()
        self.message_count = 0

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
            client.subscribe(MQTT_TOPIC)
            logger.info(f"Subscribed to {MQTT_TOPIC}")
        else:
            logger.error(f"MQTT connection failed with code {rc}")

    def on_message(self, client, userdata, msg):
        try:
            device_id = msg.topic.split("/")[-1]
            payload = json.loads(msg.payload.decode())

            # Validate payload
            if not all(k in payload for k in ("ts", "suhu", "rh")):
                logger.warning(f"Invalid payload from {device_id}: {payload}")
                return

            # Write to Redis
            redis_key = f"sensor:{device_id}:latest"
            self.redis.setex(redis_key, REDIS_TTL, json.dumps(payload))

            # Buffer for ClickHouse
            self.buffer.append((device_id, payload["ts"], payload["suhu"], payload["rh"]))
            self.message_count += 1

            # Flush if batch full or interval elapsed
            if len(self.buffer) >= BATCH_SIZE or (time.time() - self.last_flush) >= FLUSH_INTERVAL:
                self.flush_to_clickhouse()

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def flush_to_clickhouse(self):
        if not self.buffer:
            return
        try:
            self.ch.execute(
                "INSERT INTO sensor_data (device_id, timestamp, suhu, rh) VALUES",
                self.buffer,
            )
            logger.info(f"Flushed {len(self.buffer)} rows to ClickHouse")
        except Exception as e:
            logger.error(f"ClickHouse insert error: {e}")
        finally:
            self.buffer.clear()
            self.last_flush = time.time()

    def run(self):
        client = mqtt.Client()
        client.on_connect = self.on_connect
        client.on_message = self.on_message

        while True:
            try:
                logger.info(f"Connecting to MQTT {MQTT_BROKER}:{MQTT_PORT}...")
                client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
                client.loop_forever()
            except KeyboardInterrupt:
                logger.info("Shutting down...")
                self.flush_to_clickhouse()
                break
            except Exception as e:
                logger.error(f"MQTT connection error: {e}, retrying in 5s...")
                time.sleep(5)


if __name__ == "__main__":
    consumer = Consumer()
    consumer.run()
```

- [ ] **Step 3: Create Dockerfile**

```dockerfile
# services/consumer/Dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

- [ ] **Step 4: Add consumer to docker-compose.yml**

Add to `docker-compose.yml` services:

```yaml
  consumer:
    build:
      context: ./services/consumer
      dockerfile: Dockerfile
    container_name: bpom-consumer
    env_file: .env
    environment:
      MQTT_BROKER: emqx
      REDIS_HOST: redis
      CLICKHOUSE_HOST: clickhouse
    depends_on:
      - emqx
      - redis
      - clickhouse
    restart: unless-stopped
    networks:
      - bpom-net
```

- [ ] **Step 5: Test consumer with mock MQTT message**

```bash
# Start consumer
docker-compose up -d consumer

# Publish test message
mosquitto_pub -h localhost -t /bpom/sensor/n1 \
  -m '{"ts":"2026-07-15T10:30:00+07:00","suhu":25.3,"rh":62.1}'

# Check Redis
redis-cli GET sensor:n1:latest
# Should return: {"ts":"2026-07-15T10:30:00+07:00","suhu":25.3,"rh":62.1}

# Check ClickHouse
curl -s 'http://localhost:8123/?query=SELECT+*+FROM+bpom_sensors.sensor_data+LIMIT+5'
# Should return the inserted row

# Check consumer logs
docker-compose logs consumer --tail=5
```

- [ ] **Step 6: Commit**

```bash
git add services/consumer/
git commit -m "feat: consumer service - mqtt to redis + clickhouse"
```

---

### Task 3: Mock Sensor Script

**Files:**
- Create: `scripts/mock_sensor.py`

**Interfaces:**
- Produces: MQTT messages on `/bpom/sensor/{n1..n6}` every 60s
- Used by: Integration testing

- [ ] **Step 1: Create mock sensor script**

```python
#!/usr/bin/env python3
# scripts/mock_sensor.py
"""Mock IoT sensor — publishes random data to MQTT for testing."""
import json
import random
import time
import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT = 1883
DEVICES = ["n1", "n2", "n3", "n4", "n5", "n6"]

BASELINES = {
    "n1": {"suhu": 25.0, "rh": 60.0},
    "n2": {"suhu": 24.5, "rh": 58.0},
    "n3": {"suhu": 26.0, "rh": 62.0},
    "n4": {"suhu": 23.5, "rh": 55.0},
    "n5": {"suhu": 25.5, "rh": 61.0},
    "n6": {"suhu": 24.0, "rh": 57.0},
}


def generate_reading(device_id: str, anomaly: bool = False) -> dict:
    base = BASELINES[device_id]
    if anomaly:
        suhu = base["suhu"] + random.uniform(-5, 10)
        rh = base["rh"] + random.uniform(-10, 15)
    else:
        suhu = base["suhu"] + random.gauss(0, 0.5)
        rh = base["rh"] + random.gauss(0, 1.0)
    return {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S+07:00"),
        "suhu": round(suhu, 2),
        "rh": round(rh, 2),
    }


def main():
    client = mqtt.Client()
    client.connect(BROKER, PORT)
    client.loop_start()
    print(f"Publishing to {BROKER}:{PORT}, devices: {DEVICES}")

    tick = 0
    try:
        while True:
            for device in DEVICES:
                # Inject anomaly ~5% of the time
                anomaly = random.random() < 0.05
                reading = generate_reading(device, anomaly)
                topic = f"/bpom/sensor/{device}"
                client.publish(topic, json.dumps(reading))
                status = "ANOMALY" if anomaly else "normal"
                print(f"[{tick}] {topic}: {reading['suhu']}°C, {reading['rh']}%RH ({status})")
            tick += 1
            time.sleep(10)  # 10s for testing, change to 60 for production cadence
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test mock sensor**

```bash
# In terminal 1: start infra
docker-compose up -d

# In terminal 2: start mock sensor
pip install paho-mqtt
python scripts/mock_sensor.py

# In terminal 3: verify data flowing
redis-cli GET sensor:n1:latest
# Should show JSON with suhu and rh
```

- [ ] **Step 3: Commit**

```bash
git add scripts/mock_sensor.py
git commit -m "feat: mock sensor script for testing"
```

---

### Task 4: Inference Service — ONNX Model + Alert Writing

**Files:**
- Create: `services/inference/main.py`
- Create: `services/inference/api.py`
- Create: `services/inference/requirements.txt`
- Create: `services/inference/Dockerfile`
- Create: `configs/thresholds.yaml`

**Interfaces:**
- Consumes: Redis keys `sensor:{id}:latest` (JSON)
- Produces: MySQL `alerts` table rows, FastAPI endpoints `GET /health`, `GET /scores/latest`

- [ ] **Step 1: Create thresholds config**

```yaml
# configs/thresholds.yaml
# Threshold per-device — diisi dari hasil training (validasi split)
# Placeholder values untuk testing

thresholds:
  n1: 0.030
  n2: 0.025
  n3: 0.028
  n4: 0.032
  n5: 0.027
  n6: 0.029
```

- [ ] **Step 2: Create requirements.txt**

```
# services/inference/requirements.txt
fastapi==0.109.0
uvicorn==0.27.0
onnxruntime==1.17.0
redis==5.0.0
pymysql==1.1.0
numpy==1.26.0
pyyaml==6.0.1
```

- [ ] **Step 3: Create `main.py`**

```python
# services/inference/main.py
"""
Inference Service — polls Redis for latest sensor values,
runs ONNX model, writes alerts to MySQL when score > threshold.
"""
import json
import logging
import os
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
import pymysql
import redis
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))
MYSQL_DB = os.environ.get("MYSQL_DATABASE", os.environ.get("MYSQL_DB", "bpom_web"))
MYSQL_USER = os.environ.get("MYSQL_USER", "bpom")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "bpom_secret")
MODEL_PATH = os.environ.get("MODEL_PATH", "./models/best_model.onnx")
CONFIG_PATH = os.environ.get("CONFIG_PATH", "./configs/thresholds.yaml")
SCALER_PATH = os.environ.get("SCALER_PATH", "./models/scalers.npz")
INFERENCE_INTERVAL = int(os.environ.get("INFERENCE_INTERVAL", 60))
WINDOW_SIZE = int(os.environ.get("WINDOW_SIZE", 30))
DEVICES = [f"n{i}" for i in range(1, 7)]


class InferenceEngine:
    def __init__(self, model_path: str, thresholds: dict):
        self.thresholds = thresholds
        self.windows: dict[str, list] = {d: [] for d in DEVICES}
        self.scalers = None
        self.session = None

        # Load ONNX model
        if Path(model_path).exists():
            self.session = ort.InferenceSession(model_path)
            logger.info(f"Loaded ONNX model from {model_path}")
        else:
            logger.warning(f"Model not found at {model_path} — running in mock mode")

        # Load scalers
        if Path(SCALER_PATH).exists():
            self.scalers = np.load(SCALER_PATH)
            logger.info(f"Loaded scalers from {SCALER_PATH}")
        else:
            logger.warning(f"Scalers not found at {SCALER_PATH} — using raw values")

    def update_window(self, device_id: str, suhu: float, rh: float):
        window = self.windows[device_id]
        window.append([suhu, rh])
        if len(window) > WINDOW_SIZE:
            window.pop(0)

    def infer(self, device_id: str) -> float | None:
        window = self.windows[device_id]
        if len(window) < WINDOW_SIZE:
            return None

        data = np.array(window, dtype=np.float32)

        # Normalize if scalers available
        if self.scalers is not None:
            mean = self.scalers[f"{device_id}_mean"]
            std = self.scalers[f"{device_id}_std"]
            data = (data - mean) / std

        # Reshape: (batch=1, channels=2, timesteps=30)
        input_data = data.T[np.newaxis, ...]

        if self.session is not None:
            input_name = self.session.get_inputs()[0].name
            reconstruction = self.session.run(None, {input_name: input_data})[0]
            score = float(np.mean((input_data - reconstruction) ** 2))
        else:
            # Mock mode: random score
            score = float(np.random.uniform(0, 0.05))

        return score


class AlertWriter:
    def __init__(self):
        self.conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            database=MYSQL_DB,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
        )
        logger.info(f"Connected to MySQL {MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}")

    def write_alert(self, device_id: str, score: float, threshold: float, channel: str = "global"):
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO alerts (device_id, detected_at, score, threshold, channel, status, created_at, updated_at)
                   VALUES (%s, NOW(), %s, %s, %s, 'active', NOW(), NOW())""",
                (device_id, score, threshold, channel),
            )
        logger.warning(f"ALERT: {device_id} score={score:.6f} > threshold={threshold}")

    def ensure_connection(self):
        try:
            self.conn.ping(reconnect=True)
        except Exception:
            self.conn = pymysql.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                database=MYSQL_DB,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True,
            )


class InferenceLoop:
    def __init__(self):
        self.redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        thresholds = self._load_thresholds()
        self.engine = InferenceEngine(MODEL_PATH, thresholds)
        self.alert_writer = AlertWriter()

    def _load_thresholds(self) -> dict:
        with open(CONFIG_PATH) as f:
            config = yaml.safe_load(f)
        return config.get("thresholds", {d: 0.03 for d in DEVICES})

    def poll_and_infer(self):
        for device_id in DEVICES:
            raw = self.redis.get(f"sensor:{device_id}:latest")
            if not raw:
                continue

            data = json.loads(raw)
            self.engine.update_window(device_id, data["suhu"], data["rh"])

            score = self.engine.infer(device_id)
            if score is None:
                continue

            threshold = self.engine.thresholds.get(device_id, 0.03)
            if score > threshold:
                self.alert_writer.ensure_connection()
                self.alert_writer.write_alert(device_id, score, threshold)

    def run(self):
        logger.info(f"Inference loop started — interval={INFERENCE_INTERVAL}s, window={WINDOW_SIZE}")
        while True:
            try:
                self.poll_and_infer()
            except Exception as e:
                logger.error(f"Inference error: {e}")
            time.sleep(INFERENCE_INTERVAL)


# Global instances for API
_redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
_thresholds = {}
_engine = None


def get_engine() -> InferenceEngine:
    global _engine, _thresholds
    if _engine is None:
        if not _thresholds:
            with open(CONFIG_PATH) as f:
                _thresholds = yaml.safe_load(f).get("thresholds", {})
        _engine = InferenceEngine(MODEL_PATH, _thresholds)
    return _engine


if __name__ == "__main__":
    loop = InferenceLoop()
    loop.run()
```

- [ ] **Step 4: Create `api.py`**

```python
# services/inference/api.py
"""FastAPI endpoints for inference service."""
import json
import os

from fastapi import FastAPI

from main import DEVICES, get_engine, _redis

app = FastAPI(title="BPOM Inference Service", version="1.0.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/scores/latest")
def latest_scores():
    """Debug endpoint: return latest anomaly scores for all devices."""
    engine = get_engine()
    scores = {}
    for device_id in DEVICES:
        raw = _redis.get(f"sensor:{device_id}:latest")
        if not raw:
            scores[device_id] = {"score": None, "threshold": engine.thresholds.get(device_id, 0.03), "anomaly": None}
            continue

        data = json.loads(raw)
        engine.update_window(device_id, data["suhu"], data["rh"])
        score = engine.infer(device_id)
        threshold = engine.thresholds.get(device_id, 0.03)
        scores[device_id] = {
            "score": score,
            "threshold": threshold,
            "anomaly": score > threshold if score is not None else None,
        }
    return scores


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

- [ ] **Step 5: Create Dockerfile**

```dockerfile
# services/inference/Dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "main.py"]
```

- [ ] **Step 6: Add inference to docker-compose.yml**

```yaml
  inference:
    build:
      context: ./services/inference
      dockerfile: Dockerfile
    container_name: bpom-inference
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      REDIS_HOST: redis
      MYSQL_HOST: mysql
    volumes:
      - ./models:/models:ro
      - ./configs:/config:ro
    depends_on:
      - redis
      - mysql
    restart: unless-stopped
    networks:
      - bpom-net
```

- [ ] **Step 7: Create MySQL alerts table**

Wait for MySQL to be ready, then create the table:

```bash
docker-compose exec mysql mysql -u bpom -pbpom_secret bpom_web -e "
CREATE TABLE IF NOT EXISTS alerts (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    device_id VARCHAR(20) NOT NULL,
    detected_at TIMESTAMP NOT NULL,
    score DOUBLE NOT NULL,
    threshold DOUBLE NOT NULL,
    channel VARCHAR(10) DEFAULT 'global',
    status ENUM('active', 'acknowledged', 'resolved') DEFAULT 'active',
    notes TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_device_time (device_id, detected_at),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"
```

- [ ] **Step 8: Test inference service end-to-end**

```bash
# Start all services
docker-compose up -d

# Run mock sensor for ~2 minutes to fill window
python scripts/mock_sensor.py &
sleep 130

# Check inference logs
docker-compose logs inference --tail=10

# Check for alerts in MySQL
docker-compose exec mysql mysql -u bpom -pbpom_secret bpom_web \
  -e "SELECT * FROM alerts ORDER BY id DESC LIMIT 5;"

# Test API endpoint
curl http://localhost:8000/health
curl http://localhost:8000/scores/latest
```

- [ ] **Step 9: Commit**

```bash
git add services/inference/ configs/thresholds.yaml
git commit -m "feat: inference service - onnx model + alert writing"
```

---

### Task 5: Laravel Web Application

**Files:**
- Create: `web/` (Laravel 12 + Breeze + React scaffold)
- Create: `web/app/Http/Controllers/DashboardController.php`
- Create: `web/app/Http/Controllers/AlertController.php`
- Create: `web/app/Http/Controllers/SensorApiController.php`
- Create: `web/app/Models/Alert.php`
- Create: `web/app/Services/RedisSensorService.php`
- Create: `web/resources/js/Pages/Dashboard.jsx`
- Create: `web/resources/js/Pages/Alerts/Index.jsx`
- Create: `web/resources/js/Components/DeviceCard.jsx`
- Create: `web/resources/js/Components/AlertTable.jsx`
- Create: `web/Dockerfile`

**Interfaces:**
- Consumes: Redis `sensor:{id}:latest`, MySQL `alerts` table
- Produces: Web dashboard on `:8080`, API endpoints `GET /api/sensors/latest`, `GET /api/alerts`

- [ ] **Step 1: Scaffold Laravel with Breeze**

```bash
cd /media/dandy/College/SEMESTER_VIII/anomaly-detection
composer create-project laravel/laravel web
cd web
composer require laravel/breeze --dev
php artisan breeze:install react
npm install
php artisan key:generate
```

- [ ] **Step 2: Install Redis and MySQL dependencies**

```bash
cd web
composer require predis/predis
```

- [ ] **Step 3: Configure `.env` for Laravel**

Update `web/.env`:

```env
APP_NAME="BPOM Monitor"
APP_URL=http://localhost:8080

DB_CONNECTION=mysql
DB_HOST=mysql
DB_PORT=3306
DB_DATABASE=bpom_web
DB_USERNAME=bpom
DB_PASSWORD=bpom_secret

REDIS_HOST=redis
REDIS_PORT=6379
```

- [ ] **Step 4: Create Alert model and migration**

```bash
cd web
php artisan make:model Alert -m
```

Edit the migration file:

```php
<?php
// web/database/migrations/xxxx_xx_xx_create_alerts_table.php
use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        Schema::create('alerts', function (Blueprint $table) {
            $table->id();
            $table->string('device_id', 20)->index();
            $table->timestamp('detected_at')->index();
            $table->double('score');
            $table->double('threshold');
            $table->string('channel', 10)->default('global');
            $table->enum('status', ['active', 'acknowledged', 'resolved'])->default('active');
            $table->text('notes')->nullable();
            $table->timestamps();

            $table->index(['device_id', 'detected_at']);
            $table->index('status');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('alerts');
    }
};
```

Edit the Alert model:

```php
<?php
// web/app/Models/Alert.php
namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class Alert extends Model
{
    protected $fillable = [
        'device_id', 'detected_at', 'score', 'threshold',
        'channel', 'status', 'notes',
    ];

    protected $casts = [
        'detected_at' => 'datetime',
        'score' => 'double',
        'threshold' => 'double',
    ];

    public function scopeActive($query)
    {
        return $query->where('status', 'active');
    }

    public function scopeForDevice($query, string $deviceId)
    {
        return $query->where('device_id', $deviceId);
    }
}
```

Note: Do NOT run `php artisan migrate` — the table is already created by Task 4 Step 7. The migration file exists for documentation.

- [ ] **Step 5: Create RedisSensorService**

```php
<?php
// web/app/Services/RedisSensorService.php
namespace App\Services;

use Illuminate\Support\Facades\Redis;

class RedisSensorService
{
    private const DEVICES = ['n1', 'n2', 'n3', 'n4', 'n5', 'n6'];
    private const KEY_PATTERN = 'sensor:%s:latest';

    public function getAllLatest(): array
    {
        $result = [];
        foreach (self::DEVICES as $device) {
            $result[$device] = $this->getLatest($device);
        }
        return $result;
    }

    public function getLatest(string $device): ?array
    {
        $key = sprintf(self::KEY_PATTERN, $device);
        $raw = Redis::get($key);
        return $raw ? json_decode($raw, true) : null;
    }
}
```

- [ ] **Step 6: Create controllers**

```php
<?php
// web/app/Http/Controllers/DashboardController.php
namespace App\Http\Controllers;

use App\Models\Alert;
use Illuminate\Http\Request;
use Inertia\Inertia;

class DashboardController extends Controller
{
    public function index()
    {
        return Inertia::render('Dashboard', [
            'devices' => ['n1', 'n2', 'n3', 'n4', 'n5', 'n6'],
            'activeAlerts' => Alert::active()->count(),
        ]);
    }
}
```

```php
<?php
// web/app/Http/Controllers/AlertController.php
namespace App\Http\Controllers;

use App\Models\Alert;
use Illuminate\Http\Request;

class AlertController extends Controller
{
    public function index(Request $request)
    {
        $query = Alert::orderBy('detected_at', 'desc');

        if ($request->has('device_id')) {
            $query->where('device_id', $request->device_id);
        }
        if ($request->has('status')) {
            $query->where('status', $request->status);
        }

        $alerts = $query->paginate(20);

        return inertia('Alerts/Index', [
            'alerts' => $alerts,
            'filters' => $request->only(['device_id', 'status']),
        ]);
    }

    public function acknowledge(Alert $alert)
    {
        $alert->update(['status' => 'acknowledged']);
        return back();
    }

    public function resolve(Alert $alert)
    {
        $alert->update(['status' => 'resolved']);
        return back();
    }
}
```

```php
<?php
// web/app/Http/Controllers/SensorApiController.php
namespace App\Http\Controllers;

use App\Services\RedisSensorService;
use Illuminate\Http\Request;

class SensorApiController extends Controller
{
    public function latest(RedisSensorService $redis)
    {
        return response()->json($redis->getAllLatest());
    }
}
```

- [ ] **Step 7: Register routes**

```php
<?php
// web/routes/web.php
use App\Http\Controllers\DashboardController;
use App\Http\Controllers\AlertController;
use Illuminate\Support\Facades\Route;

Route::get('/', function () {
    return redirect()->route('dashboard');
});

Route::middleware('auth')->group(function () {
    Route::get('/dashboard', [DashboardController::class, 'index'])->name('dashboard');
    Route::get('/alerts', [AlertController::class, 'index'])->name('alerts.index');
    Route::patch('/alerts/{alert}/acknowledge', [AlertController::class, 'acknowledge'])->name('alerts.acknowledge');
    Route::patch('/alerts/{alert}/resolve', [AlertController::class, 'resolve'])->name('alerts.resolve');
});

require __DIR__.'/auth.php';
```

```php
<?php
// web/routes/api.php
use App\Http\Controllers\SensorApiController;
use Illuminate\Support\Facades\Route;

Route::middleware('auth:sanctum')->group(function () {
    Route::get('/sensors/latest', [SensorApiController::class, 'latest']);
});
```

- [ ] **Step 8: Create Dashboard page (React)**

```jsx
// web/resources/js/Pages/Dashboard.jsx
import { useEffect, useState } from 'react';
import AuthenticatedLayout from '@/Layouts/AuthenticatedLayout';
import { Head } from '@inertiajs/react';
import DeviceCard from '@/Components/DeviceCard';

export default function Dashboard({ devices, activeAlerts }) {
    const [sensorData, setSensorData] = useState({});

    useEffect(() => {
        const fetchData = async () => {
            try {
                const res = await fetch('/api/sensors/latest');
                const data = await res.json();
                setSensorData(data);
            } catch (e) {
                console.error('Failed to fetch sensor data:', e);
            }
        };

        fetchData();
        const interval = setInterval(fetchData, 10000);
        return () => clearInterval(interval);
    }, []);

    return (
        <AuthenticatedLayout
            header={<h2 className="text-xl font-semibold leading-tight text-gray-800">Dashboard</h2>}
        >
            <Head title="Dashboard" />

            <div className="py-6">
                <div className="mx-auto max-w-7xl sm:px-6 lg:px-8">
                    <div className="mb-6 overflow-hidden bg-white shadow-sm sm:rounded-lg">
                        <div className="p-6">
                            <p className="text-lg font-semibold text-gray-700">
                                Active Alerts:{' '}
                                <span className={activeAlerts > 0 ? 'text-red-600' : 'text-green-600'}>
                                    {activeAlerts}
                                </span>
                            </p>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
                        {devices.map((device) => (
                            <DeviceCard
                                key={device}
                                deviceId={device}
                                data={sensorData[device]}
                            />
                        ))}
                    </div>
                </div>
            </div>
        </AuthenticatedLayout>
    );
}
```

- [ ] **Step 9: Create DeviceCard component**

```jsx
// web/resources/js/Components/DeviceCard.jsx
export default function DeviceCard({ deviceId, data }) {
    const isOnline = data !== null;

    return (
        <div className={`overflow-hidden rounded-lg border-2 shadow-sm ${
            isOnline ? 'border-green-200 bg-green-50' : 'border-gray-200 bg-gray-50'
        }`}>
            <div className="p-4">
                <div className="mb-3 flex items-center justify-between">
                    <h3 className="text-lg font-bold text-gray-800">
                        {deviceId.toUpperCase()}
                    </h3>
                    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        isOnline ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                    }`}>
                        {isOnline ? 'Online' : 'Offline'}
                    </span>
                </div>

                {isOnline ? (
                    <div className="space-y-2">
                        <div className="flex justify-between">
                            <span className="text-sm text-gray-500">Suhu</span>
                            <span className="font-mono text-sm font-semibold">
                                {data.suhu?.toFixed(1)}°C
                            </span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-sm text-gray-500">RH</span>
                            <span className="font-mono text-sm font-semibold">
                                {data.rh?.toFixed(1)}%
                            </span>
                        </div>
                        <p className="text-xs text-gray-400">{data.ts}</p>
                    </div>
                ) : (
                    <p className="text-sm italic text-gray-400">No data available</p>
                )}
            </div>
        </div>
    );
}
```

- [ ] **Step 10: Create Alerts/Index page**

```jsx
// web/resources/js/Pages/Alerts/Index.jsx
import AuthenticatedLayout from '@/Layouts/AuthenticatedLayout';
import { Head, router } from '@inertiajs/react';

export default function Index({ alerts, filters }) {
    const handleAcknowledge = (alertId) => {
        router.patch(`/alerts/${alertId}/acknowledge`);
    };

    const handleResolve = (alertId) => {
        router.patch(`/alerts/${alertId}/resolve`);
    };

    const handleFilter = (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        router.get('/alerts', Object.fromEntries(formData));
    };

    return (
        <AuthenticatedLayout
            header={<h2 className="text-xl font-semibold leading-tight text-gray-800">Alerts</h2>}
        >
            <Head title="Alerts" />

            <div className="py-6">
                <div className="mx-auto max-w-7xl sm:px-6 lg:px-8">
                    <div className="mb-4 overflow-hidden bg-white shadow-sm sm:rounded-lg">
                        <form onSubmit={handleFilter} className="flex gap-4 p-4">
                            <select name="device_id" defaultValue={filters.device_id || ''} className="rounded border-gray-300 text-sm">
                                <option value="">Semua Device</option>
                                {['n1','n2','n3','n4','n5','n6'].map(d => (
                                    <option key={d} value={d}>{d.toUpperCase()}</option>
                                ))}
                            </select>
                            <select name="status" defaultValue={filters.status || ''} className="rounded border-gray-300 text-sm">
                                <option value="">Semua Status</option>
                                <option value="active">Active</option>
                                <option value="acknowledged">Acknowledged</option>
                                <option value="resolved">Resolved</option>
                            </select>
                            <button type="submit" className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700">
                                Filter
                            </button>
                        </form>
                    </div>

                    <div className="overflow-hidden bg-white shadow-sm sm:rounded-lg">
                        <table className="min-w-full divide-y divide-gray-200">
                            <thead className="bg-gray-50">
                                <tr>
                                    <th className="px-6 py-3 text-left text-xs font-medium uppercase text-gray-500">Device</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium uppercase text-gray-500">Detected At</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium uppercase text-gray-500">Score</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium uppercase text-gray-500">Threshold</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium uppercase text-gray-500">Status</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium uppercase text-gray-500">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-200">
                                {alerts.data.map((alert) => (
                                    <tr key={alert.id}>
                                        <td className="px-6 py-4 text-sm font-medium text-gray-900">{alert.device_id.toUpperCase()}</td>
                                        <td className="px-6 py-4 text-sm text-gray-500">{alert.detected_at}</td>
                                        <td className="px-6 py-4 font-mono text-sm text-red-600">{alert.score.toFixed(6)}</td>
                                        <td className="px-6 py-4 font-mono text-sm text-gray-500">{alert.threshold.toFixed(6)}</td>
                                        <td className="px-6 py-4">
                                            <span className={`inline-flex rounded-full px-2 text-xs font-semibold leading-5 ${
                                                alert.status === 'active' ? 'bg-red-100 text-red-800' :
                                                alert.status === 'acknowledged' ? 'bg-yellow-100 text-yellow-800' :
                                                'bg-green-100 text-green-800'
                                            }`}>
                                                {alert.status}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 text-sm">
                                            {alert.status === 'active' && (
                                                <button onClick={() => handleAcknowledge(alert.id)} className="mr-2 text-blue-600 hover:text-blue-900">Ack</button>
                                            )}
                                            {alert.status !== 'resolved' && (
                                                <button onClick={() => handleResolve(alert.id)} className="text-green-600 hover:text-green-900">Resolve</button>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </AuthenticatedLayout>
    );
}
```

- [ ] **Step 11: Create Laravel Dockerfile**

```dockerfile
# web/Dockerfile
FROM php:8.3-apache

RUN apt-get update && apt-get install -y \
    git curl zip unzip libpng-dev libonig-dev libxml2-dev libzip-dev \
    && docker-php-ext-install pdo_mysql mbstring exif pcntl bcmath gd zip \
    && pecl install redis && docker-php-ext-enable redis

COPY --from=composer:latest /usr/bin/composer /usr/bin/composer

WORKDIR /var/www/html
COPY . .
RUN composer install --no-dev --optimize-autoloader
RUN npm ci && npm run build

RUN chown -R www-data:www-data /var/www/html/storage /var/www/html/bootstrap/cache
RUN a2enmod rewrite

EXPOSE 80
```

- [ ] **Step 12: Add Laravel to docker-compose.yml**

```yaml
  laravel:
    build:
      context: ./web
      dockerfile: Dockerfile
    container_name: bpom-web
    ports:
      - "8080:80"
    env_file: .env
    environment:
      APP_ENV: local
      APP_DEBUG: "true"
      DB_CONNECTION: mysql
      DB_HOST: mysql
      DB_PORT: 3306
      DB_DATABASE: bpom_web
      DB_USERNAME: bpom
      DB_PASSWORD: bpom_secret
      REDIS_HOST: redis
    depends_on:
      - mysql
      - redis
    restart: unless-stopped
    networks:
      - bpom-net
```

- [ ] **Step 13: Test Laravel dashboard**

```bash
# Start everything
docker-compose up -d

# Run mock sensor in background
python scripts/mock_sensor.py &
sleep 15

# Open browser
# http://localhost:8080 — should show login page
# Register a user, login, see dashboard with 6 device cards

# Check API
curl -b cookies.txt http://localhost:8080/api/sensors/latest
```

- [ ] **Step 14: Commit**

```bash
git add web/
git commit -m "feat: laravel dashboard with auth, device cards, alert list"
```

---

### Task 6: Integration Testing & Polish

**Files:**
- Create: `scripts/test_e2e.sh`

**Interfaces:**
- Consumes: All services running
- Produces: Verified end-to-end data flow

- [ ] **Step 1: Create end-to-end test script**

```bash
#!/bin/bash
# scripts/test_e2e.sh
set -e

echo "=== BPOM IoT Anomaly Detection — E2E Test ==="

echo "[1/6] Checking infrastructure..."
docker-compose ps | grep -q "bpom-emqx.*Up" || (echo "FAIL: emqx not running" && exit 1)
docker-compose ps | grep -q "bpom-redis.*Up" || (echo "FAIL: redis not running" && exit 1)
docker-compose ps | grep -q "bpom-clickhouse.*Up" || (echo "FAIL: clickhouse not running" && exit 1)
docker-compose ps | grep -q "bpom-mysql.*Up" || (echo "FAIL: mysql not running" && exit 1)
echo "  PASS: All infrastructure services running"

echo "[2/6] Testing EMQX..."
curl -sf http://localhost:18083/api/v5/status > /dev/null || (echo "FAIL: emqx api" && exit 1)
echo "  PASS: EMQX responding"

echo "[3/6] Testing MQTT publish + consumer..."
mosquitto_pub -h localhost -t /bpom/sensor/n1 \
  -m '{"ts":"2026-07-15T10:30:00+07:00","suhu":25.3,"rh":62.1}'
sleep 2
REDIS_VAL=$(redis-cli GET sensor:n1:latest)
echo "$REDIS_VAL" | grep -q "suhu" || (echo "FAIL: redis not updated" && exit 1)
echo "  PASS: MQTT → Redis working"

echo "[4/6] Testing ClickHouse..."
CH_VAL=$(curl -sf 'http://localhost:8123/?query=SELECT+count()+FROM+bpom_sensors.sensor_data')
echo "  PASS: ClickHouse has $CH_VAL rows"

echo "[5/6] Testing Inference API..."
curl -sf http://localhost:8000/health | grep -q "ok" || (echo "FAIL: inference health" && exit 1)
echo "  PASS: Inference service responding"

echo "[6/6] Testing Laravel..."
curl -sf http://localhost:8080 > /dev/null || (echo "FAIL: laravel" && exit 1)
echo "  PASS: Laravel responding"

echo ""
echo "=== All tests passed ==="
```

- [ ] **Step 2: Run full integration test**

```bash
chmod +x scripts/test_e2e.sh
./scripts/test_e2e.sh
```

- [ ] **Step 3: Verify alerts appear in Laravel**

```bash
# Wait for anomaly injection from mock sensor (~2 min)
sleep 130

# Check MySQL for alerts
docker-compose exec mysql mysql -u bpom -pbpom_secret bpom_web \
  -e "SELECT COUNT(*) as total FROM alerts;"

# Open browser: http://localhost:8080/alerts
# Should see alert entries if mock sensor injected anomalies
```

- [ ] **Step 4: Final commit**

```bash
git add scripts/test_e2e.sh
git commit -m "feat: e2e integration test script"
```

---

## Summary

| Task | Description | Dependencies |
|---|---|---|
| 1 | Docker infrastructure (EMQX, Redis, ClickHouse, MySQL) | None |
| 2 | Consumer service (MQTT → Redis + ClickHouse) | Task 1 |
| 3 | Mock sensor script | Task 1 |
| 4 | Inference service (ONNX + alert writing) | Task 1, 2 |
| 5 | Laravel web application | Task 1, 4 |
| 6 | Integration testing | All |

**Parallelizable:** Tasks 2 and 3 can run in parallel after Task 1. Task 5 can start scaffold while Task 4 is in progress.

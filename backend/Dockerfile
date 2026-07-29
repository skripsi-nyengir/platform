FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY anomaly_backend ./anomaly_backend
COPY anomaly_worker ./anomaly_worker
RUN pip install --disable-pip-version-check --no-cache-dir .

FROM base AS test

ENV EDA_TOOLCHAIN_ROLE=api

RUN pip install --disable-pip-version-check --no-cache-dir ".[test]"
COPY alembic.ini ./
COPY migrations ./migrations
COPY tests ./tests
CMD ["pytest", "-q"]

FROM base AS runtime

COPY alembic.ini ./
COPY migrations ./migrations
CMD ["uvicorn", "anomaly_backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM python:3.12-slim AS worker

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN pip install --disable-pip-version-check --no-cache-dir \
    "psycopg[binary]==3.3.2" \
    "sqlalchemy==2.0.51" \
    "numpy==2.4.6"
RUN pip install --disable-pip-version-check --no-cache-dir \
    "torch==2.13.0" --index-url https://download.pytorch.org/whl/cu130
COPY anomaly_backend ./anomaly_backend
COPY anomaly_worker ./anomaly_worker
CMD ["python", "-m", "anomaly_worker.service"]

FROM worker AS worker-test

RUN pip install --disable-pip-version-check --no-cache-dir \
    "pytest==9.1.0"
COPY tests/test_preview_simulator.py ./worker_tests/test_preview_simulator.py
COPY tests/test_import_transform.py ./worker_tests/test_import_transform.py
COPY tests/test_scorer_protocol.py ./worker_tests/test_scorer_protocol.py
CMD ["pytest", "-q", "worker_tests"]

FROM worker AS eda-worker

COPY --from=ghcr.io/astral-sh/uv:0.11.6 /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
COPY alembic.ini ./
COPY migrations ./migrations
COPY anomaly_eda ./anomaly_eda
ENV EDA_TOOLCHAIN_ROLE=eda-worker \
    PATH="/app/.venv/bin:$PATH"
RUN uv sync --frozen --no-dev --no-editable --extra eda --extra test
COPY tests ./tests
CMD ["python", "-m", "anomaly_worker.eda_service"]

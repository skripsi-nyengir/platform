import os
from dataclasses import dataclass

from sqlalchemy import URL


@dataclass(frozen=True, slots=True)
class Settings:
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str
    eda_worker_lease_seconds: int = 900
    eda_worker_heartbeat_seconds: int = 30
    eda_worker_max_attempts: int = 3
    eda_worker_compute_timeout_seconds: int = 1_800

    def __post_init__(self) -> None:
        worker_values = {
            "lease": self.eda_worker_lease_seconds,
            "heartbeat": self.eda_worker_heartbeat_seconds,
            "max attempts": self.eda_worker_max_attempts,
            "compute timeout": self.eda_worker_compute_timeout_seconds,
        }
        if any(value < 1 for value in worker_values.values()):
            raise ValueError("EDA worker settings must be positive integers")
        if self.eda_worker_heartbeat_seconds >= self.eda_worker_lease_seconds:
            raise ValueError("EDA worker heartbeat must be shorter than its lease")

    @classmethod
    def from_environ(cls) -> "Settings":
        return cls(
            postgres_host=os.environ["POSTGRES_HOST"],
            postgres_port=int(os.environ["POSTGRES_PORT"]),
            postgres_db=os.environ["POSTGRES_DB"],
            postgres_user=os.environ["POSTGRES_USER"],
            postgres_password=os.environ["POSTGRES_PASSWORD"],
            eda_worker_lease_seconds=int(
                os.environ.get("EDA_WORKER_LEASE_SECONDS", "900")
            ),
            eda_worker_heartbeat_seconds=int(
                os.environ.get("EDA_WORKER_HEARTBEAT_SECONDS", "30")
            ),
            eda_worker_max_attempts=int(
                os.environ.get("EDA_WORKER_MAX_ATTEMPTS", "3")
            ),
            eda_worker_compute_timeout_seconds=int(
                os.environ.get("EDA_WORKER_COMPUTE_TIMEOUT_SECONDS", "1800")
            ),
        )

    @property
    def async_database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )

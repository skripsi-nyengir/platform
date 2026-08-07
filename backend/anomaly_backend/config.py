import os
from dataclasses import dataclass

from sqlalchemy import URL


def _boolean_environ(variable: str, default: bool) -> bool:
    # A misspelt value must not silently resolve to False; dropping the Secure cookie
    # attribute because of a typo would be invisible until it mattered.
    raw = os.environ.get(variable)
    if raw is None:
        return default
    normalised = raw.strip().lower()
    if normalised in {"true", "1", "yes"}:
        return True
    if normalised in {"false", "0", "no"}:
        return False
    raise ValueError(f"{variable} must be a boolean value")


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
    auth_cookie_secure: bool = True
    auth_session_ttl_seconds: int = 43_200
    auth_max_failed_attempts: int = 5
    auth_lockout_seconds: int = 900
    notifications_enabled: bool = False
    slack_bot_token: str = ""
    slack_channel_id: str = ""
    notifier_poll_seconds: int = 15
    notifier_lease_seconds: int = 120
    notifier_max_attempts: int = 5
    notifier_chart_margin_minutes: int = 15
    notifier_max_episode_age_minutes: int = 60

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
        auth_values = {
            "session TTL": self.auth_session_ttl_seconds,
            "max failed attempts": self.auth_max_failed_attempts,
            "lockout": self.auth_lockout_seconds,
        }
        if any(value < 1 for value in auth_values.values()):
            raise ValueError("Authentication settings must be positive integers")
        notifier_values = {
            "poll interval": self.notifier_poll_seconds,
            "lease": self.notifier_lease_seconds,
            "max attempts": self.notifier_max_attempts,
            "chart margin": self.notifier_chart_margin_minutes,
            "max episode age": self.notifier_max_episode_age_minutes,
        }
        if any(value < 1 for value in notifier_values.values()):
            raise ValueError("Notifier settings must be positive integers")
        if self.notifier_lease_seconds <= self.notifier_poll_seconds:
            raise ValueError("Notifier lease must be longer than its poll interval")
        # Refusing here rather than starting quietly: a notifier that is enabled but
        # cannot reach Slack looks healthy while every alert goes unsent.
        if self.notifications_enabled and not (
            self.slack_bot_token and self.slack_channel_id
        ):
            raise ValueError(
                "SLACK_BOT_TOKEN and SLACK_CHANNEL_ID are required when "
                "NOTIFICATIONS_ENABLED is true"
            )

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
            auth_cookie_secure=_boolean_environ("AUTH_COOKIE_SECURE", True),
            auth_session_ttl_seconds=int(
                os.environ.get("AUTH_SESSION_TTL_SECONDS", "43200")
            ),
            auth_max_failed_attempts=int(
                os.environ.get("AUTH_MAX_FAILED_ATTEMPTS", "5")
            ),
            auth_lockout_seconds=int(os.environ.get("AUTH_LOCKOUT_SECONDS", "900")),
            notifications_enabled=_boolean_environ("NOTIFICATIONS_ENABLED", False),
            slack_bot_token=os.environ.get("SLACK_BOT_TOKEN", ""),
            slack_channel_id=os.environ.get("SLACK_CHANNEL_ID", ""),
            notifier_poll_seconds=int(os.environ.get("NOTIFIER_POLL_SECONDS", "15")),
            notifier_lease_seconds=int(os.environ.get("NOTIFIER_LEASE_SECONDS", "120")),
            notifier_max_attempts=int(os.environ.get("NOTIFIER_MAX_ATTEMPTS", "5")),
            notifier_chart_margin_minutes=int(
                os.environ.get("NOTIFIER_CHART_MARGIN_MINUTES", "15")
            ),
            notifier_max_episode_age_minutes=int(
                os.environ.get("NOTIFIER_MAX_EPISODE_AGE_MINUTES", "60")
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

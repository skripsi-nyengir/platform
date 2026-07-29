from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import (
    DOUBLE_PRECISION,
    JSONB,
    TIMESTAMP,
    TSRANGE,
    UUID,
)


metadata = MetaData()

_FINITE_SCORE_CHECK = (
    "score > '-Infinity'::double precision "
    "AND score < 'Infinity'::double precision"
)
_FINITE_THRESHOLD_CHECK = (
    "threshold > '-Infinity'::double precision "
    "AND threshold < 'Infinity'::double precision"
)
_FINITE_TEMPERATURE_CHECK = (
    "temperature_c > '-Infinity'::double precision "
    "AND temperature_c < 'Infinity'::double precision"
)
_FINITE_HUMIDITY_CHECK = (
    "relative_humidity_pct > '-Infinity'::double precision "
    "AND relative_humidity_pct < 'Infinity'::double precision"
)
_SHA256_CHECK = "{column} ~ '^[0-9a-f]{{64}}$'"
_EDA_PERIOD_KIND_CHECK = (
    "period_kind IN ('daily', 'weekly', 'monthly', 'custom', 'full_range')"
)
_EDA_SECTION_CHECK = (
    "section IN ("
    "'quality_overview', 'joint_density', 'univariate', "
    "'quality_excerpt', 'temporal_coverage', 'temporal_distribution', "
    "'relationships', 'stationarity', 'change_points', 'uncertainty', "
    "'audit_metadata')"
)


devices = Table(
    "devices",
    metadata,
    Column("device_id", Text, primary_key=True),
    Column("display_name", Text, nullable=False),
    Column("source_device_uuid", Text),
    Column("time_zone", Text),
    Column("telemetry_kind", Text, nullable=False),
    Column("is_active", Boolean, nullable=False),
    Column("archived_at", DateTime(timezone=True)),
    CheckConstraint(
        "telemetry_kind IN ('historical_replay', 'anomaly_injected')",
        name="ck_devices_telemetry_kind",
    ),
    CheckConstraint(
        "(is_active AND archived_at IS NULL) OR "
        "(NOT is_active AND archived_at IS NOT NULL)",
        name="ck_devices_archive_state",
    ),
)
Index(
    "uq_devices_one_active_per_kind",
    devices.c.telemetry_kind,
    devices.c.is_active,
    unique=True,
    postgresql_where=devices.c.is_active,
)

corpora = Table(
    "corpora",
    metadata,
    Column("corpus_id", Text, primary_key=True),
    Column("device_id", Text, ForeignKey("devices.device_id"), nullable=False),
    Column("status", Text, nullable=False),
    Column("archive_sha256", Text, nullable=False),
    Column("member_sha256", Text),
    Column("preprocessing_contract_version", Text, nullable=False),
    Column("source_device_uuid", Text),
    Column("time_zone", Text),
    Column("interval_start", DateTime(timezone=False)),
    Column("interval_end", DateTime(timezone=False)),
    Column("filter_config", JSONB, nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True)),
    Column("accepted_count", BigInteger, nullable=False),
    Column("ignored_index_count", BigInteger, nullable=False),
    Column("rejection_counts", JSONB, nullable=False),
    CheckConstraint(
        "status IN ('staging', 'published', 'failed')",
        name="ck_corpora_status",
    ),
    CheckConstraint(
        "accepted_count >= 0 AND ignored_index_count >= 0",
        name="ck_corpora_counts",
    ),
    UniqueConstraint(
        "device_id",
        "archive_sha256",
        "preprocessing_contract_version",
        name="uq_corpora_identity",
    ),
)

injection_events = Table(
    "injection_events",
    metadata,
    Column("event_id", Text, primary_key=True),
    Column("corpus_id", Text, ForeignKey("corpora.corpus_id"), nullable=False),
    Column("device_id", Text, ForeignKey("devices.device_id"), nullable=False),
    Column("family", Text, nullable=False),
    Column("severity", Text, nullable=False),
    Column("channel", Text, nullable=False),
    Column("channel_index", Integer, nullable=False),
    Column("start_idx", BigInteger, nullable=False),
    Column("end_idx_exclusive", BigInteger, nullable=False),
    Column("start_ts", DateTime(timezone=False), nullable=False),
    Column("end_ts", DateTime(timezone=False), nullable=False),
    Column("segment_index", Integer, nullable=False),
    CheckConstraint(
        "end_idx_exclusive > start_idx AND start_idx >= 0",
        name="ck_injection_events_range",
    ),
    CheckConstraint(
        "severity IN ('low', 'medium', 'high')",
        name="ck_injection_events_severity",
    ),
    CheckConstraint(
        "family IN ('spike', 'drift', 'stuck', 'erratic', 'bias', "
        "'data_loss', 'garbage')",
        name="ck_injection_events_family",
    ),
)
Index(
    "ix_injection_events_corpus",
    injection_events.c.corpus_id,
    injection_events.c.start_idx,
)

published_corpora = Table(
    "published_corpora",
    metadata,
    Column(
        "device_id", Text, ForeignKey("devices.device_id"), primary_key=True
    ),
    Column(
        "corpus_id",
        Text,
        ForeignKey("corpora.corpus_id"),
        nullable=False,
        unique=True,
    ),
    Column("published_at", DateTime(timezone=True), nullable=False),
)

preprocessing_snapshots = Table(
    "preprocessing_snapshots",
    metadata,
    Column(
        "corpus_id", Text, ForeignKey("corpora.corpus_id"), primary_key=True
    ),
    Column("channels", JSONB, nullable=False),
    Column("window_size", Integer, nullable=False),
    Column("stride", Integer, nullable=False),
    Column("segment_metadata", JSONB, nullable=False),
    Column("split_boundaries", JSONB, nullable=False),
    Column("split_counts", JSONB, nullable=False),
    Column("scaler", JSONB, nullable=False),
    CheckConstraint(
        "window_size = 30 AND stride = 1",
        name="ck_preprocessing_window_stride",
    ),
)

telemetry = Table(
    "telemetry",
    metadata,
    Column("device_id", Text, ForeignKey("devices.device_id"), primary_key=True),
    Column("ts", DateTime(timezone=False), primary_key=True),
    Column("temperature_c", Float),
    Column("relative_humidity_pct", Float),
    Column("payload_hash", Text, nullable=False),
    Column("source_index", BigInteger, nullable=False),
    Column("corpus_id", Text, ForeignKey("corpora.corpus_id"), nullable=False),
    Column("corpus_index", BigInteger, nullable=False),
    Column("segment_id", Integer, nullable=False),
    Column("dataset_split", Text, nullable=False),
    CheckConstraint(
        _FINITE_TEMPERATURE_CHECK,
        name="ck_telemetry_temperature_c_finite",
    ),
    CheckConstraint(
        _FINITE_HUMIDITY_CHECK,
        name="ck_telemetry_relative_humidity_pct_finite",
    ),
    CheckConstraint("source_index >= 0", name="ck_telemetry_source_index"),
    CheckConstraint(
        "corpus_index >= 0 AND segment_id >= 0",
        name="ck_telemetry_corpus_index",
    ),
    CheckConstraint(
        "dataset_split IN ('legacy', 'train', 'validation', 'test')",
        name="ck_telemetry_dataset_split",
    ),
)
Index(
    "ix_telemetry_corpus_index",
    telemetry.c.corpus_id,
    telemetry.c.corpus_index,
)

eda_source_snapshots = Table(
    "eda_source_snapshots",
    metadata,
    Column(
        "id",
        UUID(as_uuid=True),
        server_default=text("gen_random_uuid()"),
        primary_key=True,
    ),
    Column("dataset_id", Text, nullable=False),
    Column("source_sha256", Text, nullable=False),
    Column("manifest_sha256", Text, nullable=False),
    Column("config_hash", Text, nullable=False),
    Column("source_from_ts", TIMESTAMP(timezone=False, precision=0), nullable=False),
    Column("source_to_ts", TIMESTAMP(timezone=False, precision=0), nullable=False),
    Column("expected_row_count", BigInteger, nullable=False),
    Column("expected_channel_count", Integer, nullable=False),
    Column("importer_version", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    ),
    Column("completed_at", DateTime(timezone=True)),
    Column("manifest", JSONB, nullable=False),
    CheckConstraint(
        "dataset_id <> '' AND importer_version <> ''",
        name="ck_eda_source_snapshots_names",
    ),
    CheckConstraint(
        _SHA256_CHECK.format(column="source_sha256"),
        name="ck_eda_source_snapshots_source_sha256",
    ),
    CheckConstraint(
        _SHA256_CHECK.format(column="manifest_sha256"),
        name="ck_eda_source_snapshots_manifest_sha256",
    ),
    CheckConstraint(
        _SHA256_CHECK.format(column="config_hash"),
        name="ck_eda_source_snapshots_config_hash",
    ),
    CheckConstraint(
        "source_from_ts <= source_to_ts",
        name="ck_eda_source_snapshots_bounds",
    ),
    CheckConstraint(
        "expected_row_count > 0 AND expected_channel_count > 0",
        name="ck_eda_source_snapshots_expected_counts",
    ),
    CheckConstraint(
        "status IN ('staging', 'complete', 'failed')",
        name="ck_eda_source_snapshots_status",
    ),
    CheckConstraint(
        "(status = 'staging' AND completed_at IS NULL) OR "
        "(status IN ('complete', 'failed') AND completed_at IS NOT NULL)",
        name="ck_eda_source_snapshots_completion",
    ),
    CheckConstraint(
        "jsonb_typeof(manifest) = 'object'",
        name="ck_eda_source_snapshots_manifest_object",
    ),
    UniqueConstraint(
        "dataset_id",
        "source_sha256",
        name="uq_eda_source_snapshots_dataset_source",
    ),
    UniqueConstraint(
        "id",
        "source_sha256",
        name="uq_eda_source_snapshots_id_source",
    ),
)

eda_raw_readings = Table(
    "eda_raw_readings",
    metadata,
    Column(
        "snapshot_id",
        UUID(as_uuid=True),
        ForeignKey("eda_source_snapshots.id", name="fk_eda_raw_readings_snapshot"),
        primary_key=True,
    ),
    Column("source_row_number", BigInteger, primary_key=True),
    Column("device_id", Text, nullable=False),
    Column("data_index", Integer, nullable=False),
    Column("value", DOUBLE_PRECISION, nullable=False),
    Column(
        "ts",
        TIMESTAMP(timezone=False, precision=0),
        primary_key=True,
    ),
    Column("is_connected", Boolean, nullable=False),
    CheckConstraint(
        "source_row_number > 0",
        name="ck_eda_raw_readings_source_row_number",
    ),
    CheckConstraint(
        "device_id <> ''",
        name="ck_eda_raw_readings_device_id",
    ),
    CheckConstraint(
        "data_index IN (0, 1)",
        name="ck_eda_raw_readings_data_index",
    ),
)
Index(
    "ix_eda_raw_readings_snapshot_device_ts_data_index",
    eda_raw_readings.c.snapshot_id,
    eda_raw_readings.c.device_id,
    eda_raw_readings.c.ts,
    eda_raw_readings.c.data_index,
)

eda_jobs = Table(
    "eda_jobs",
    metadata,
    Column(
        "id",
        UUID(as_uuid=True),
        server_default=text("gen_random_uuid()"),
        primary_key=True,
    ),
    Column("logical_key", Text, nullable=False),
    Column("snapshot_id", UUID(as_uuid=True), nullable=False),
    Column("source_sha256", Text, nullable=False),
    Column("from_ts", TIMESTAMP(timezone=False, precision=0), nullable=False),
    Column("to_ts", TIMESTAMP(timezone=False, precision=0), nullable=False),
    Column("period_kind", Text, nullable=False),
    Column("algorithm_version", Text, nullable=False),
    Column("config_hash", Text, nullable=False),
    Column("status", Text, server_default="queued", nullable=False),
    Column("attempt_count", Integer, server_default="0", nullable=False),
    Column("max_attempts", Integer, server_default="3", nullable=False),
    Column("trigger_kind", Text, nullable=False),
    Column("lease_owner", Text),
    Column("lease_until", DateTime(timezone=True)),
    Column("terminal", Boolean, server_default=text("false"), nullable=False),
    Column("error_code", Text),
    Column("error_detail", Text),
    Column(
        "created_at",
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    ),
    Column("started_at", DateTime(timezone=True)),
    Column("completed_at", DateTime(timezone=True)),
    CheckConstraint(
        _SHA256_CHECK.format(column="logical_key"),
        name="ck_eda_jobs_logical_key",
    ),
    CheckConstraint(
        _SHA256_CHECK.format(column="source_sha256"),
        name="ck_eda_jobs_source_sha256",
    ),
    CheckConstraint(
        _SHA256_CHECK.format(column="config_hash"),
        name="ck_eda_jobs_config_hash",
    ),
    CheckConstraint("from_ts < to_ts", name="ck_eda_jobs_range"),
    CheckConstraint(_EDA_PERIOD_KIND_CHECK, name="ck_eda_jobs_period_kind"),
    CheckConstraint(
        "algorithm_version <> '' AND trigger_kind <> ''",
        name="ck_eda_jobs_names",
    ),
    CheckConstraint(
        "status IN ('queued', 'running', 'succeeded', 'failed')",
        name="ck_eda_jobs_status",
    ),
    CheckConstraint(
        "attempt_count >= 0 AND max_attempts > 0 "
        "AND attempt_count <= max_attempts",
        name="ck_eda_jobs_attempts",
    ),
    CheckConstraint(
        "terminal = (status IN ('succeeded', 'failed')) "
        "AND ((terminal AND completed_at IS NOT NULL) "
        "OR (NOT terminal AND completed_at IS NULL))",
        name="ck_eda_jobs_terminal",
    ),
    CheckConstraint(
        "(status = 'running' AND lease_owner IS NOT NULL "
        "AND lease_until IS NOT NULL) OR "
        "(status <> 'running' AND lease_owner IS NULL "
        "AND lease_until IS NULL)",
        name="ck_eda_jobs_lease",
    ),
    ForeignKeyConstraint(
        ["snapshot_id", "source_sha256"],
        ["eda_source_snapshots.id", "eda_source_snapshots.source_sha256"],
        name="fk_eda_jobs_snapshot_source",
    ),
)
Index(
    "uq_eda_jobs_active_logical_key",
    eda_jobs.c.logical_key,
    unique=True,
    postgresql_where=eda_jobs.c.status.in_(("queued", "running")),
)

eda_runs = Table(
    "eda_runs",
    metadata,
    Column(
        "id",
        UUID(as_uuid=True),
        server_default=text("gen_random_uuid()"),
        primary_key=True,
    ),
    Column("logical_key", Text, nullable=False),
    Column("snapshot_id", UUID(as_uuid=True), nullable=False),
    Column("source_sha256", Text, nullable=False),
    Column("from_ts", TIMESTAMP(timezone=False, precision=0), nullable=False),
    Column("to_ts", TIMESTAMP(timezone=False, precision=0), nullable=False),
    Column("period_kind", Text, nullable=False),
    Column("algorithm_version", Text, nullable=False),
    Column("config_hash", Text, nullable=False),
    Column("provenance", JSONB, nullable=False),
    Column("canonical_release", Boolean, server_default=text("false"), nullable=False),
    Column("completed_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        _SHA256_CHECK.format(column="logical_key"),
        name="ck_eda_runs_logical_key",
    ),
    CheckConstraint(
        _SHA256_CHECK.format(column="source_sha256"),
        name="ck_eda_runs_source_sha256",
    ),
    CheckConstraint(
        _SHA256_CHECK.format(column="config_hash"),
        name="ck_eda_runs_config_hash",
    ),
    CheckConstraint("from_ts < to_ts", name="ck_eda_runs_range"),
    CheckConstraint(_EDA_PERIOD_KIND_CHECK, name="ck_eda_runs_period_kind"),
    CheckConstraint(
        "algorithm_version <> ''",
        name="ck_eda_runs_algorithm_version",
    ),
    CheckConstraint(
        "jsonb_typeof(provenance) = 'object'",
        name="ck_eda_runs_provenance_object",
    ),
    CheckConstraint(
        "NOT canonical_release OR period_kind = 'full_range'",
        name="ck_eda_runs_canonical_release",
    ),
    ForeignKeyConstraint(
        ["snapshot_id", "source_sha256"],
        ["eda_source_snapshots.id", "eda_source_snapshots.source_sha256"],
        name="fk_eda_runs_snapshot_source",
    ),
    UniqueConstraint("logical_key", name="uq_eda_runs_logical_key"),
)

eda_result_sections = Table(
    "eda_result_sections",
    metadata,
    Column("run_id", UUID(as_uuid=True), nullable=False),
    Column("section", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("reason_code", Text),
    Column("reason_detail", Text),
    Column("payload", JSONB),
    Column("payload_sha256", Text),
    Column(
        "created_at",
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    ),
    CheckConstraint(_EDA_SECTION_CHECK, name="ck_eda_result_sections_section"),
    CheckConstraint(
        "status IN ('complete', 'not_eligible', 'failed')",
        name="ck_eda_result_sections_status",
    ),
    CheckConstraint(
        "payload_sha256 IS NULL OR "
        + _SHA256_CHECK.format(column="payload_sha256"),
        name="ck_eda_result_sections_payload_sha256",
    ),
    CheckConstraint(
        "(status = 'complete' AND reason_code IS NULL "
        "AND reason_detail IS NULL AND payload IS NOT NULL "
        "AND payload_sha256 IS NOT NULL "
        "AND jsonb_typeof(payload) = 'object') OR "
        "(status IN ('not_eligible', 'failed') "
        "AND reason_code IS NOT NULL AND reason_detail IS NOT NULL "
        "AND payload IS NULL AND payload_sha256 IS NULL)",
        name="ck_eda_result_sections_content",
    ),
    ForeignKeyConstraint(
        ["run_id"],
        ["eda_runs.id"],
        name="fk_eda_result_sections_run",
    ),
    UniqueConstraint(
        "run_id",
        "section",
        name="uq_eda_result_sections_run_section",
    ),
)

model_families = Table(
    "model_families",
    metadata,
    Column("model_key", Text, primary_key=True),
    Column("display_name", Text, nullable=False),
    Column("is_public", Boolean, nullable=False),
)

model_versions = Table(
    "model_versions",
    metadata,
    Column("version", Text, primary_key=True),
    Column(
        "model_key",
        Text,
        ForeignKey("model_families.model_key"),
        nullable=False,
    ),
    Column("runtime_kind", Text, nullable=False),
    Column("is_selectable", Boolean, nullable=False),
    Column("adapter_key", Text, nullable=False),
    Column("schema_version", Text, nullable=False),
    Column("channels", JSONB, nullable=False),
    Column("window_size", Integer, nullable=False),
    Column("stride", Integer, nullable=False),
    Column("score_key", Text, nullable=False),
    Column("score_semantics", Text, nullable=False),
    Column("threshold", Float, nullable=False),
    Column("threshold_policy", JSONB, nullable=False),
    Column("temporal_semantics", Text, nullable=False),
    Column("source_commit", Text),
    Column("source_config", Text),
    Column("manifest_sha256", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "runtime_kind IN ('legacy_fixture', 'preview_simulator', 'artifact')",
        name="ck_model_versions_runtime_kind",
    ),
    CheckConstraint(
        "temporal_semantics IN ('context_end', 'next_target')",
        name="ck_model_versions_temporal_semantics",
    ),
    CheckConstraint(
        "window_size > 0 AND stride > 0",
        name="ck_model_versions_window_stride",
    ),
    CheckConstraint(
        _FINITE_THRESHOLD_CHECK,
        name="ck_model_versions_threshold_finite",
    ),
)

model_activations = Table(
    "model_activations",
    metadata,
    Column("activation_id", Text, primary_key=True),
    Column("command_id", Text, nullable=False, unique=True),
    Column("payload_hash", Text, nullable=False),
    Column("device_id", Text, ForeignKey("devices.device_id"), nullable=False),
    Column(
        "prior_model_version", Text, ForeignKey("model_versions.version")
    ),
    Column(
        "model_version",
        Text,
        ForeignKey("model_versions.version"),
        nullable=False,
    ),
    Column("changed", Boolean, nullable=False),
    Column("activated_at", DateTime(timezone=True), nullable=False),
    Column("actor", Text, nullable=False),
)

active_model_selections = Table(
    "active_model_selections",
    metadata,
    Column(
        "device_id", Text, ForeignKey("devices.device_id"), primary_key=True
    ),
    Column(
        "activation_id",
        Text,
        ForeignKey("model_activations.activation_id"),
        nullable=False,
        unique=True,
    ),
    Column(
        "model_version",
        Text,
        ForeignKey("model_versions.version"),
        nullable=False,
    ),
)

replay_jobs = Table(
    "replay_jobs",
    metadata,
    Column("job_id", Text, primary_key=True),
    Column("logical_job_hash", Text, nullable=False),
    Column("device_id", Text, ForeignKey("devices.device_id"), nullable=False),
    Column("corpus_id", Text, ForeignKey("corpora.corpus_id"), nullable=False),
    Column("archive_sha256", Text, nullable=False),
    Column("preprocessing_contract_version", Text, nullable=False),
    Column(
        "activation_id",
        Text,
        ForeignKey("model_activations.activation_id"),
        nullable=False,
    ),
    Column(
        "model_version",
        Text,
        ForeignKey("model_versions.version"),
        nullable=False,
    ),
    Column("score_provenance", Text, nullable=False),
    Column("from_ts", DateTime(timezone=False), nullable=False),
    Column("to_ts", DateTime(timezone=False), nullable=False),
    Column(
        "replay_range",
        TSRANGE,
        Computed("tsrange(from_ts, to_ts, '[)')", persisted=True),
        nullable=False,
    ),
    Column("status", Text, nullable=False),
    Column("lease_owner", Text),
    Column("lease_expires_at", DateTime(timezone=True)),
    Column("heartbeat_at", DateTime(timezone=True)),
    Column("attempt_count", Integer, nullable=False),
    Column("max_attempts", Integer, nullable=False),
    Column("next_corpus_index", BigInteger, nullable=False),
    Column("processed_count", BigInteger, nullable=False),
    Column("result_count", BigInteger, nullable=False),
    Column("episode_count", BigInteger, nullable=False),
    Column("submitted_at", DateTime(timezone=True), nullable=False),
    Column("started_at", DateTime(timezone=True)),
    Column("completed_at", DateTime(timezone=True)),
    Column("error_code", Text),
    Column("error_detail", Text),
    CheckConstraint(
        "status IN ('queued', 'running', 'succeeded', 'failed')",
        name="ck_replay_jobs_status",
    ),
    CheckConstraint("from_ts < to_ts", name="ck_replay_jobs_range"),
    CheckConstraint(
        "to_ts - from_ts <= interval '31 days'",
        name="ck_replay_jobs_max_range",
    ),
    CheckConstraint(
        "score_provenance IN ('simulated_preview', 'artifact_backed')",
        name="ck_replay_jobs_provenance",
    ),
    CheckConstraint(
        "attempt_count >= 0 AND max_attempts > 0 "
        "AND attempt_count <= max_attempts",
        name="ck_replay_jobs_attempts",
    ),
    CheckConstraint(
        "next_corpus_index >= 0 AND processed_count >= 0 "
        "AND result_count >= 0 AND episode_count >= 0",
        name="ck_replay_jobs_progress",
    ),
)
Index(
    "uq_replay_jobs_logical_nonfailed",
    replay_jobs.c.logical_job_hash,
    unique=True,
    postgresql_where=replay_jobs.c.status != "failed",
)

replay_commands = Table(
    "replay_commands",
    metadata,
    Column("command_id", Text, primary_key=True),
    Column("payload_hash", Text, nullable=False),
    Column("job_id", Text, ForeignKey("replay_jobs.job_id"), nullable=False),
    Column("accepted_at", DateTime(timezone=True), nullable=False),
)
Index("ix_replay_commands_job", replay_commands.c.job_id)

replay_result_staging = Table(
    "replay_result_staging",
    metadata,
    Column("job_id", Text, ForeignKey("replay_jobs.job_id"), primary_key=True),
    Column("score_ts", DateTime(timezone=False), primary_key=True),
    Column("window_start_ts", DateTime(timezone=False), nullable=False),
    Column("window_end_ts", DateTime(timezone=False), nullable=False),
    Column("model_version", Text, nullable=False),
    Column("score", Float, nullable=False),
    Column("threshold", Float, nullable=False),
    Column("is_anomaly", Boolean, nullable=False),
    Column("score_provenance", Text, nullable=False),
    Column("source_start_index", BigInteger, nullable=False),
    Column("source_end_index", BigInteger, nullable=False),
    Column("reading_count", Integer, nullable=False),
    Column("stride", Integer, nullable=False),
    Column("segment_id", Integer, nullable=False),
    Column("eligible_window_ordinal", BigInteger, nullable=False),
    Column("recon_temperature_c", Float, nullable=True),
    Column("recon_relative_humidity_pct", Float, nullable=True),
    Column("band_half_temperature_c", Float, nullable=True),
    Column("band_half_relative_humidity_pct", Float, nullable=True),
    CheckConstraint(
        _FINITE_SCORE_CHECK, name="ck_replay_result_staging_score_finite"
    ),
    CheckConstraint(
        _FINITE_THRESHOLD_CHECK,
        name="ck_replay_result_staging_threshold_finite",
    ),
)

replay_episode_staging = Table(
    "replay_episode_staging",
    metadata,
    Column("job_id", Text, ForeignKey("replay_jobs.job_id"), primary_key=True),
    Column("episode_ordinal", Integer, primary_key=True),
    Column("segment_id", Integer, nullable=False),
    Column("episode_start_ts", DateTime(timezone=False), nullable=False),
    Column("episode_end_ts", DateTime(timezone=False), nullable=False),
    Column("last_score_ts", DateTime(timezone=False), nullable=False),
    Column("first_window_start_ts", DateTime(timezone=False), nullable=False),
    Column("first_window_end_ts", DateTime(timezone=False), nullable=False),
    Column("peak_score", Float, nullable=False),
    Column("latest_score", Float, nullable=False),
    Column("anomalous_window_count", Integer, nullable=False),
    Column("closure_reason", Text, nullable=False),
    CheckConstraint(
        "closure_reason IN ('normal', 'gap', 'replay_end')",
        name="ck_replay_episode_staging_closure",
    ),
)

replay_episode_checkpoints = Table(
    "replay_episode_checkpoints",
    metadata,
    Column("job_id", Text, ForeignKey("replay_jobs.job_id"), primary_key=True),
    Column("state", JSONB, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

worker_heartbeats = Table(
    "worker_heartbeats",
    metadata,
    Column("worker_id", Text, primary_key=True),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("heartbeat_at", DateTime(timezone=True), nullable=False),
)

inference_results = Table(
    "inference_results",
    metadata,
    Column("device_id", Text, ForeignKey("devices.device_id"), primary_key=True),
    Column("corpus_id", Text, ForeignKey("corpora.corpus_id"), nullable=False),
    Column("window_start_ts", DateTime(timezone=False), nullable=False),
    Column("window_end_ts", DateTime(timezone=False), nullable=False),
    Column("score_ts", DateTime(timezone=False), primary_key=True),
    Column("model_version", Text, ForeignKey("model_versions.version"), primary_key=True),
    Column("score", Float, nullable=False),
    Column("threshold", Float, nullable=False),
    Column("is_anomaly", Boolean, nullable=False),
    Column("score_provenance", Text, nullable=False),
    Column("source_start_index", BigInteger, nullable=False),
    Column("source_end_index", BigInteger, nullable=False),
    Column("reading_count", Integer, nullable=False),
    Column("stride", Integer, nullable=False),
    Column("segment_id", Integer, nullable=False),
    Column("replay_job_id", Text, ForeignKey("replay_jobs.job_id")),
    Column("recon_temperature_c", Float, nullable=True),
    Column("recon_relative_humidity_pct", Float, nullable=True),
    Column("band_half_temperature_c", Float, nullable=True),
    Column("band_half_relative_humidity_pct", Float, nullable=True),
    CheckConstraint(
        _FINITE_SCORE_CHECK, name="ck_inference_results_m2_score_finite"
    ),
    CheckConstraint(
        _FINITE_THRESHOLD_CHECK,
        name="ck_inference_results_m2_threshold_finite",
    ),
    CheckConstraint(
        "window_start_ts < window_end_ts",
        name="ck_inference_results_m2_window_order",
    ),
    CheckConstraint(
        "score_provenance IN ("
        "'deterministic_threshold_fixture', "
        "'simulated_preview', 'artifact_backed')",
        name="ck_inference_results_m2_provenance",
    ),
    CheckConstraint(
        "source_start_index >= 0 "
        "AND source_start_index <= source_end_index "
        "AND reading_count > 0 AND stride > 0 AND segment_id >= 0",
        name="ck_inference_results_m2_window_shape",
    ),
)
Index(
    "ix_inference_results_replay",
    inference_results.c.replay_job_id,
    inference_results.c.score_ts,
)

alerts = Table(
    "alerts",
    metadata,
    Column("alert_id", Text, primary_key=True),
    Column("device_id", Text, ForeignKey("devices.device_id"), nullable=False),
    Column("detected_at", DateTime(timezone=False)),
    Column("score", Float, nullable=False),
    Column("threshold", Float, nullable=False),
    Column(
        "model_version",
        Text,
        ForeignKey("model_versions.version"),
        nullable=False,
    ),
    Column("inference_result_window_start_ts", DateTime(timezone=False), nullable=False),
    Column("inference_result_window_end_ts", DateTime(timezone=False), nullable=False),
    Column("detection_basis", Text, nullable=False),
    Column("corpus_id", Text, ForeignKey("corpora.corpus_id"), nullable=False),
    Column("episode_start_ts", DateTime(timezone=False), nullable=False),
    Column("episode_end_ts", DateTime(timezone=False), nullable=False),
    Column("last_score_ts", DateTime(timezone=False), nullable=False),
    Column("created_at", DateTime(timezone=True)),
    Column("peak_score", Float, nullable=False),
    Column("latest_score", Float, nullable=False),
    Column("anomalous_window_count", Integer, nullable=False),
    Column("replay_job_id", Text, ForeignKey("replay_jobs.job_id")),
    Column("segment_id", Integer, nullable=False),
    Column("closure_reason", Text, nullable=False),
    CheckConstraint(_FINITE_SCORE_CHECK, name="ck_alerts_score_finite"),
    CheckConstraint(_FINITE_THRESHOLD_CHECK, name="ck_alerts_threshold_finite"),
    CheckConstraint(
        "inference_result_window_start_ts < inference_result_window_end_ts",
        name="ck_alerts_window_order",
    ),
    CheckConstraint(
        "detection_basis IN ("
        "'threshold_model_fixture', 'simulated_preview', 'artifact_backed')",
        name="ck_alerts_detection_basis",
    ),
    CheckConstraint(
        "("
        "detection_basis = 'threshold_model_fixture' "
        "AND detected_at IS NOT NULL AND created_at IS NULL "
        "AND replay_job_id IS NULL "
        "AND closure_reason = 'legacy_m1_fixture'"
        ") OR ("
        "detection_basis IN ('simulated_preview', 'artifact_backed') "
        "AND detected_at IS NULL AND created_at IS NOT NULL "
        "AND replay_job_id IS NOT NULL "
        "AND closure_reason IN ('normal', 'gap', 'replay_end')"
        ")",
        name="ck_alerts_lineage_time_domain",
    ),
)
Index("ix_alerts_current_order", alerts.c.detected_at.desc(), alerts.c.alert_id)
Index(
    "ix_alerts_episode_order",
    alerts.c.episode_end_ts.desc(),
    alerts.c.alert_id,
)

alert_events = Table(
    "alert_events",
    metadata,
    Column("event_id", Text, primary_key=True),
    Column("alert_id", Text, ForeignKey("alerts.alert_id"), nullable=False),
    Column("event_ts", DateTime(timezone=False)),
    Column("event_at", DateTime(timezone=True)),
    Column("time_domain", Text, nullable=False),
    Column("event_type", Text, nullable=False),
    Column("device_id", Text, ForeignKey("devices.device_id"), nullable=False),
    Column("actor", Text, nullable=False),
    Column("note", Text),
    Column("inference_result_window_start_ts", DateTime(timezone=False)),
    Column("inference_result_window_end_ts", DateTime(timezone=False)),
    Column("inference_model_version", Text),
    Column("detection_basis", Text, nullable=False),
    CheckConstraint(
        "event_type IN ('detected', 'acknowledged', 'resolved')",
        name="ck_alert_events_event_type",
    ),
    CheckConstraint(
        "detection_basis IN ("
        "'threshold_model_fixture', 'simulated_preview', 'artifact_backed')",
        name="ck_alert_events_detection_basis",
    ),
    CheckConstraint(
        "(time_domain = 'legacy_naive' "
        "AND event_ts IS NOT NULL AND event_at IS NULL) OR "
        "(time_domain = 'utc' "
        "AND event_ts IS NULL AND event_at IS NOT NULL)",
        name="ck_alert_events_time_domain",
    ),
)
Index(
    "ix_alert_events_alert_latest",
    alert_events.c.alert_id,
    alert_events.c.event_ts.desc(),
    alert_events.c.event_id.desc(),
)
Index(
    "ix_alert_events_time_order",
    alert_events.c.event_ts,
    alert_events.c.event_id,
)
Index(
    "ix_alert_events_event_at",
    alert_events.c.event_at,
    alert_events.c.event_id,
)

alert_commands = Table(
    "alert_commands",
    metadata,
    Column("command_id", Text, primary_key=True),
    Column("alert_id", Text, ForeignKey("alerts.alert_id"), nullable=False),
    Column("action", Text, nullable=False),
    Column("event_ts", DateTime(timezone=False)),
    Column("accepted_at", DateTime(timezone=True)),
    Column("time_domain", Text, nullable=False),
    Column("payload_hash", Text, nullable=False),
    Column("note", Text),
    Column("accepted_event_id", Text, ForeignKey("alert_events.event_id")),
    CheckConstraint(
        "action IN ('acknowledged', 'resolved')",
        name="ck_alert_commands_action",
    ),
    CheckConstraint(
        "(time_domain = 'legacy_naive' "
        "AND event_ts IS NOT NULL AND accepted_at IS NULL) OR "
        "(time_domain = 'utc' "
        "AND event_ts IS NULL AND accepted_at IS NOT NULL)",
        name="ck_alert_commands_time_domain",
    ),
)
Index("ix_alert_commands_alert_id", alert_commands.c.alert_id)

model_evaluations = Table(
    "model_evaluations",
    metadata,
    Column("version", Text, primary_key=True),
    Column("model", Text, nullable=False),
    Column("track", Text, nullable=False),
    Column("label", Text, nullable=False),
    Column("score_key", Text, nullable=False),
    Column("score_semantics", Text, nullable=False),
    Column("evaluation_period", Text, nullable=False),
    Column("validation_only", Boolean, nullable=False),
    Column("test_evaluated", Boolean, nullable=False),
    Column("n_val_windows", Integer, nullable=False),
    Column("threshold", Float, nullable=False),
    Column("threshold_policy", JSONB, nullable=False),
    Column("has_labeled_ground_truth", Boolean, nullable=False),
    Column("available_metrics", JSONB, nullable=False),
    Column("summary", Text, nullable=False),
    Column("model_hash", Text),
    Column("preprocessing_hash", Text),
    Column("threshold_hash", Text),
    Column("metrics", JSONB, nullable=False),
    Column("notes", Text),
    Column("model_key", Text),
    Column("report_source", Text, nullable=False),
    Column("label_source", Text, nullable=False),
    Column("evaluation_kind", Text, nullable=False),
    Column("test_observed", Boolean, nullable=False),
    Column("independent_final", Boolean, nullable=False),
    Column("source_commit", Text),
    Column("source_path", Text),
    Column("source_sha256", Text),
    Column("is_public", Boolean, nullable=False),
    CheckConstraint(
        _FINITE_THRESHOLD_CHECK,
        name="ck_model_evaluations_threshold_finite",
    ),
    CheckConstraint("n_val_windows > 0", name="ck_model_evaluations_n_val_windows"),
    CheckConstraint(
        "report_source IN ("
        "'legacy_m1_fixture', 'platform_computed', 'reported_dandy_pilot')",
        name="ck_model_evaluations_report_source",
    ),
    CheckConstraint(
        "label_source IN ('none', 'synthetic_injection', 'expert', 'natural')",
        name="ck_model_evaluations_label_source",
    ),
    CheckConstraint(
        "evaluation_kind IN ("
        "'validation_threshold', 'synthetic_test', "
        "'clean_test', 'comparison_snapshot')",
        name="ck_model_evaluations_kind",
    ),
)
